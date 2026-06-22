/**
 * useVoice — core voice interaction hook.
 *
 * Architecture:
 *   Voice is a UI-only interaction layer. It:
 *     1. Captures speech via STT provider.
 *     2. Calls onTranscript(text) — the SAME handler used for text input.
 *     3. Speaks AI responses via TTS provider.
 *   It never touches LangGraph, scheduling, memory, Redis, or MongoDB.
 *
 * State machine:
 *   idle  ──[toggleMic]──▶  listening  ──[onFinal]──▶  idle  (onTranscript called)
 *   idle  ◀──[onEnd / stop]──  listening                     (silence/timeout/error)
 *   idle  ──[speakResponse]──▶  speaking  ──[TTS end]──▶  idle
 *   speaking  ──[toggleMic]──▶  listening  (interrupts TTS)
 *
 * STT callback contract (from stt.ts):
 *   onFinal  — called on successful transcription, NO onEnd follows.
 *   onEnd    — called on silence timeout, max duration, or error. NO onFinal precedes it.
 *   onError  — called with user-facing error text, ALWAYS followed by onEnd.
 *
 * Auto-speak:
 *   speakResponse() only speaks if the preceding input was via voice (wasVoiceInput
 *   flag). Text-mode users never receive unsolicited audio.
 *
 * Stale-closure safety:
 *   onTranscript is stored in a ref so changes to the callback between renders are
 *   always visible to the async onFinal handler.
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { getSTTProvider, type SpeechLanguage, type STTCallbacks } from "@/services/voice/stt";
import { getTTSProvider } from "@/services/voice/tts";

export type VoiceState = "idle" | "listening" | "speaking";

// ── Language mapping ──────────────────────────────────────────────────────────

export function toSpeechLang(lang: string | undefined): SpeechLanguage {
  if (!lang) return "en-US";
  const l = lang.toLowerCase();
  if (l === "french"  || l.startsWith("fr")) return "fr-FR";
  if (l === "arabic"  || l.startsWith("ar")) return "ar-SA";
  return "en-US";
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UseVoiceOptions {
  /** Backend language string from session memory: "english" | "french" | "arabic" */
  language?: string;
  /** Called when STT produces a final transcript — same as text input handler. */
  onTranscript: (text: string) => Promise<void>;
  /**
   * If true, speakResponse() speaks AI replies when the preceding input was voice.
   * Text-mode users are never affected. Defaults to true.
   */
  autoSpeak?: boolean;
}

export interface VoiceControls {
  voiceState:    VoiceState;
  transcript:    string;           // live interim transcript while listening
  isSupported:   boolean;          // false → hide voice UI entirely
  error:         string | null;    // mic denial / unsupported / network error
  speechLang:    SpeechLanguage;   // current BCP-47 code
  toggleMic:     () => void;
  stopSpeaking:  () => void;
  speakResponse: (text: string) => void;  // parent calls after AI message is added
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useVoice({
  language,
  onTranscript,
  autoSpeak = true,
}: UseVoiceOptions): VoiceControls {
  const stt = getSTTProvider();
  const tts = getTTSProvider();

  const [voiceState,  setVoiceState]  = useState<VoiceState>("idle");
  const [transcript,  setTranscript]  = useState("");
  const [error,       setError]       = useState<string | null>(null);
  const [speechLang,  setSpeechLang]  = useState<SpeechLanguage>(() => toSpeechLang(language));
  // isSupported starts false on both server and client to avoid SSR/hydration
  // mismatch. The useEffect below resolves the real value after mount.
  const [isSupported, setIsSupported] = useState(false);

  // Stable refs — values that must be accessible inside async/browser callbacks
  const onTranscriptRef  = useRef(onTranscript);
  const speechLangRef    = useRef(speechLang);
  const wasVoiceInputRef = useRef(false);
  const isListeningRef   = useRef(false);

  useEffect(() => { onTranscriptRef.current = onTranscript; }, [onTranscript]);
  useEffect(() => {
    const lang = toSpeechLang(language);
    setSpeechLang(lang);
    speechLangRef.current = lang;
  }, [language]);

  // Resolve browser support after mount to avoid SSR/client hydration mismatch
  useEffect(() => { setIsSupported(stt.isSupported()); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stt.stop();
      tts.stop();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stop speaking ──────────────────────────────────────────────────────────

  const stopSpeaking = useCallback(() => {
    console.debug("[useVoice] stopSpeaking");
    tts.stop();
    setVoiceState("idle");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Start listening ────────────────────────────────────────────────────────

  const startListening = useCallback(() => {
    if (!stt.isSupported()) {
      setError("Voice input is not supported in this browser. Please use Chrome or Edge.");
      return;
    }

    console.debug("[useVoice] startListening");
    setError(null);
    setTranscript("");
    isListeningRef.current = true;
    setVoiceState("listening");

    const callbacks: STTCallbacks = {

      onInterim: (t) => {
        setTranscript(t);
      },

      // Called by stt.ts ONLY on successful transcription (path A).
      // onEnd will NOT follow this call.
      onFinal: (t) => {
        console.debug("[useVoice] onFinal:", JSON.stringify(t));
        isListeningRef.current = false;
        setTranscript(t);
        setVoiceState("idle");
        if (t.trim()) {
          wasVoiceInputRef.current = true;
          // Fire-and-forget — onTranscript is the chat's handleSend
          onTranscriptRef.current(t.trim()).catch(() => {});
        }
      },

      // Called by stt.ts ONLY when there is NO final result (silence, timeout,
      // error). Always resets UI to idle. onError always precedes this call when
      // there is a user-facing message.
      onEnd: () => {
        console.debug("[useVoice] onEnd | wasListening=", isListeningRef.current);
        if (isListeningRef.current) {
          isListeningRef.current = false;
          setVoiceState("idle");
          setTranscript("");
        }
      },

      onError: (msg) => {
        console.debug("[useVoice] onError:", msg);
        isListeningRef.current = false;
        setError(msg);
        setVoiceState("idle");
        setTranscript("");
      },
    };

    stt.start(speechLangRef.current, callbacks);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stop listening (manual) ────────────────────────────────────────────────

  const stopListening = useCallback(() => {
    console.debug("[useVoice] stopListening (manual)");
    stt.stop();  // stt.stop() does NOT call any callback
    isListeningRef.current = false;
    setVoiceState("idle");
    setTranscript("");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Toggle mic ─────────────────────────────────────────────────────────────

  const toggleMic = useCallback(() => {
    setError(null);
    if (voiceState === "speaking") {
      stopSpeaking();
      startListening();
    } else if (voiceState === "listening") {
      stopListening();
    } else {
      startListening();
    }
  }, [voiceState, stopSpeaking, startListening, stopListening]);

  // ── Speak AI response ──────────────────────────────────────────────────────

  const speakResponse = useCallback(
    (text: string) => {
      if (!autoSpeak)                    return;
      if (!tts.isSupported())            return;
      if (!text)                         return;
      if (!wasVoiceInputRef.current)     return;  // text-mode → no audio
      wasVoiceInputRef.current = false;

      console.debug("[useVoice] speakResponse, lang=", speechLangRef.current);
      setVoiceState("speaking");
      tts.speak(text, speechLangRef.current, () => {
        console.debug("[useVoice] TTS ended → idle");
        setVoiceState("idle");
      });
    },
    [autoSpeak] // eslint-disable-line react-hooks/exhaustive-deps
  );

  return {
    voiceState,
    transcript,
    isSupported,
    error,
    speechLang,
    toggleMic,
    stopSpeaking,
    speakResponse,
  };
}
