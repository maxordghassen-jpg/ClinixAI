/**
 * Speech-to-Text provider abstraction.
 *
 * Default: browser-native Web Speech API (SpeechRecognition / webkitSpeechRecognition).
 * Future: swap in Whisper, OpenAI Realtime, or a local STT service by implementing
 *         the STTProvider interface and returning it from getSTTProvider().
 *
 * Multilingual: pass "en-US" | "fr-FR" | "ar-SA" as the lang argument to start().
 *
 * Lifecycle:
 *   start() → listening → onresult(isFinal) → explicit stop → onFinal callback
 *           ↓                              ↓
 *        silence timer fires           onerror fires
 *           ↓                              ↓
 *        _forceEnd → onEnd          _forceEnd → onError + onEnd
 *
 * Three stop paths:
 *   A. Final result received  → detach listeners, call rec.stop(), call onFinal. No onEnd.
 *   B. Silence / max timeout  → _forceEnd: detach, rec.stop(), call onEnd.
 *   C. Manual stop()          → detach, rec.stop(). No callback — caller manages state.
 *
 * "onend" browser event fires after every rec.stop(). Because we null out rec.onend
 * before stopping in paths A and C, the event goes nowhere. In path B we clear the
 * listener too, so onend never double-fires. In a natural no-speech end (browser fires
 * onend without us calling stop first) we check this.recognition !== null as a sentinel.
 */

export type SpeechLanguage = "en-US" | "fr-FR" | "ar-SA";

export interface STTCallbacks {
  onInterim: (transcript: string) => void;
  onFinal:   (transcript: string) => void;
  onError:   (message: string)    => void;
  onEnd:     ()                   => void;
}

export interface STTProvider {
  isSupported(): boolean;
  start(lang: SpeechLanguage, callbacks: STTCallbacks): void;
  stop(): void;
}

// ── Timeout constants ─────────────────────────────────────────────────────────

const SILENCE_TIMEOUT_MS = 2500;   // auto-stop when no new speech results for 2.5 s
const MAX_DURATION_MS    = 15000;  // absolute hard cap — release mic after 15 s

// ── Minimal local types for the Web Speech API ───────────────────────────────
// The Web Speech API is not fully typed in all lib.dom versions.

interface SpeechResultItem { readonly transcript: string; }

interface SpeechResult {
  readonly isFinal: boolean;
  [index: number]:  SpeechResultItem;
}

interface SpeechResultList {
  readonly length: number;
  [index: number]: SpeechResult;
}

interface SpeechResultEvent {
  readonly resultIndex: number;
  readonly results:     SpeechResultList;
}

interface SpeechErrorEvent { readonly error: string; }

interface SpeechRecognitionInstance {
  continuous:      boolean;
  interimResults:  boolean;
  lang:            string;
  maxAlternatives: number;
  onresult:        ((e: SpeechResultEvent) => void) | null;
  onerror:         ((e: SpeechErrorEvent)  => void) | null;
  onend:           (() => void) | null;
  start():  void;
  stop():   void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionInstance;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

// ── Web Speech API implementation ─────────────────────────────────────────────

class WebSpeechSTTProvider implements STTProvider {
  private recognition:  SpeechRecognitionInstance | null = null;
  private silenceTimer: ReturnType<typeof setTimeout>    | null = null;
  private maxTimer:     ReturnType<typeof setTimeout>    | null = null;

  isSupported(): boolean {
    return getSpeechRecognitionCtor() !== null;
  }

  start(lang: SpeechLanguage, callbacks: STTCallbacks): void {
    // Always clean up any stale instance before starting a new session
    this.stop();

    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      callbacks.onError("Speech recognition is not supported in this browser. Please use Chrome or Edge.");
      return;
    }

    const rec = new Ctor();
    this.recognition = rec;

    rec.continuous      = false;  // stop after one utterance
    rec.interimResults  = true;   // live preview while speaking
    rec.lang            = lang;
    rec.maxAlternatives = 1;

    console.debug(`[STT] starting | lang=${lang}`);

    // ── Silence timeout: auto-stop if no new results arrive ─────────────────
    const resetSilenceTimer = () => {
      if (this.silenceTimer) clearTimeout(this.silenceTimer);
      this.silenceTimer = setTimeout(() => {
        console.debug("[STT] silence timeout → stopping");
        this._forceEnd(callbacks);
      }, SILENCE_TIMEOUT_MS);
    };
    resetSilenceTimer(); // kick off immediately — handles the "no speech" case

    // ── Hard max duration ────────────────────────────────────────────────────
    this.maxTimer = setTimeout(() => {
      console.debug("[STT] max duration timeout → stopping");
      this._forceEnd(callbacks);
    }, MAX_DURATION_MS);

    // ── Result handler ───────────────────────────────────────────────────────
    rec.onresult = (event) => {
      let interim = "";
      let final   = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) final   += r[0].transcript;
        else            interim += r[0].transcript;
      }

      // Any speech activity resets the silence timer
      if (interim || final) resetSilenceTimer();

      if (interim) {
        callbacks.onInterim(interim);
      }

      if (final) {
        console.debug("[STT] final result →", JSON.stringify(final));
        // Path A: successful transcription
        // Clear timers first so they don't fire while we're cleaning up
        this._clearTimers();
        // Detach all listeners before stopping — prevents double-callbacks
        this._detach(rec);
        this.recognition = null;
        try { rec.stop(); } catch { /* already stopped */ }
        // onFinal is the terminal signal; onEnd is NOT called in this path
        callbacks.onFinal(final.trim());
      }
    };

    // ── Error handler ────────────────────────────────────────────────────────
    rec.onerror = (event) => {
      console.debug("[STT] error →", event.error);
      this._clearTimers();
      this._detach(rec);
      this.recognition = null;
      try { rec.stop(); } catch { /* already stopped */ }

      let msg: string;
      switch (event.error) {
        case "not-allowed":
        case "permission-denied":
          msg = "Microphone access denied. Please allow microphone permission and try again.";
          break;
        case "no-speech":
          // Browser detected audio but no recognisable speech — treat as silent stop
          callbacks.onEnd();
          return;
        case "network":
          msg = "Network error during transcription. Please check your connection.";
          break;
        case "audio-capture":
          msg = "Microphone not found. Please connect a microphone.";
          break;
        case "aborted":
          // Triggered by our own rec.stop() — not a user-facing error
          callbacks.onEnd();
          return;
        default:
          msg = `Speech recognition error: ${event.error}`;
      }
      callbacks.onError(msg);
      callbacks.onEnd();
    };

    // ── Natural end handler (browser fired onend before our stop) ────────────
    rec.onend = () => {
      console.debug("[STT] onend");
      this._clearTimers();
      // Only act if we haven't already cleaned up via path A or forceEnd
      if (this.recognition !== null) {
        this.recognition = null;
        callbacks.onEnd();
      }
    };

    try {
      rec.start();
    } catch (err) {
      console.debug("[STT] start() threw:", err);
      this._clearTimers();
      this._detach(rec);
      this.recognition = null;
      callbacks.onError(`Could not start recording: ${err}`);
    }
  }

  // Called by the hook when the user manually stops (toggle mic off).
  // Does NOT call any callback — the hook manages its own state on manual stop.
  stop(): void {
    console.debug("[STT] stop() called externally");
    this._clearTimers();
    if (!this.recognition) return;
    const rec = this.recognition;
    this._detach(rec);
    this.recognition = null;
    try { rec.stop(); } catch { /* already stopped */ }
  }

  // ── Private helpers ───────────────────────────────────────────────────────

  private _clearTimers(): void {
    if (this.silenceTimer) { clearTimeout(this.silenceTimer); this.silenceTimer = null; }
    if (this.maxTimer)     { clearTimeout(this.maxTimer);     this.maxTimer     = null; }
  }

  private _detach(rec: SpeechRecognitionInstance): void {
    rec.onresult = null;
    rec.onerror  = null;
    rec.onend    = null;
  }

  // Paths B: silence / max-duration timeout
  private _forceEnd(callbacks: STTCallbacks): void {
    if (!this.recognition) return;  // already ended via another path
    this._clearTimers();
    const rec = this.recognition;
    this._detach(rec);
    this.recognition = null;
    try { rec.stop(); } catch { /* already stopped */ }
    console.debug("[STT] forceEnd → onEnd");
    callbacks.onEnd();
  }
}

// ── Provider factory ──────────────────────────────────────────────────────────
// To switch providers (e.g. Whisper), replace this function:
//
//   export function getSTTProvider(): STTProvider {
//     if (process.env.NEXT_PUBLIC_STT_PROVIDER === "whisper")
//       return new WhisperSTTProvider();
//     return _default;
//   }

const _default = new WebSpeechSTTProvider();

export function getSTTProvider(): STTProvider {
  return _default;
}
