/**
 * Text-to-Speech provider abstraction.
 *
 * Default: browser-native SpeechSynthesis API.
 * Future: swap in OpenAI TTS, ElevenLabs, or Azure Cognitive Services by
 *         implementing the TTSProvider interface.
 *
 * Multilingual: voice selection prefers voices matching the target BCP-47 lang.
 * Falls back to any voice with a matching language prefix (e.g. "fr-CA" for "fr-FR"),
 * then to the browser default.
 *
 * Markdown stripping: AI responses often contain **bold**, `code`, headers etc.
 * These are stripped before synthesis so they don't get read as punctuation.
 *
 * Long response throttle: responses longer than MAX_SPEAK_CHARS are truncated.
 * A full medical consultation response can be several hundred words — speaking
 * all of it creates a poor voice UX. The threshold keeps it conversational.
 */

import type { SpeechLanguage } from "./stt";

export interface TTSProvider {
  isSupported(): boolean;
  speak(text: string, lang: SpeechLanguage, onEnd: () => void): void;
  stop(): void;
  isSpeaking(): boolean;
}

const MAX_SPEAK_CHARS = 600;

function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, "$1")          // **bold**
    .replace(/\*(.*?)\*/g,     "$1")           // *italic*
    .replace(/`{1,3}([\s\S]*?)`{1,3}/g, "$1") // `code` / ```blocks```
    .replace(/#{1,6}\s+/g,     "")             // # headings
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")  // [link](url)
    .replace(/\n{2,}/g, ". ")                  // paragraph breaks → pause
    .replace(/\n/g,     " ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

// ── Web Speech Synthesis implementation ──────────────────────────────────────

class WebSpeechTTSProvider implements TTSProvider {
  private utterance: SpeechSynthesisUtterance | null = null;

  isSupported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  speak(text: string, lang: SpeechLanguage, onEnd: () => void): void {
    if (!this.isSupported()) { onEnd(); return; }
    this.stop();

    const clean = stripMarkdown(text);
    const speakable = clean.length > MAX_SPEAK_CHARS
      ? clean.slice(0, MAX_SPEAK_CHARS) + "…"
      : clean;

    if (!speakable) { onEnd(); return; }

    this.utterance            = new SpeechSynthesisUtterance(speakable);
    this.utterance.lang       = lang;
    this.utterance.rate       = 0.95;
    this.utterance.pitch      = 1.0;
    this.utterance.volume     = 1.0;
    this.utterance.onend      = () => { this.utterance = null; onEnd(); };
    this.utterance.onerror    = () => { this.utterance = null; onEnd(); };

    // Voice selection: async-safe (voices may not be ready on first call)
    const assignVoice = () => {
      const voices = window.speechSynthesis.getVoices();
      const voice  = this._pickVoice(voices, lang);
      if (voice && this.utterance) this.utterance.voice = voice;
    };

    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      assignVoice();
      window.speechSynthesis.speak(this.utterance);
    } else {
      // Voices load asynchronously on first page load
      window.speechSynthesis.onvoiceschanged = () => {
        assignVoice();
        if (this.utterance) window.speechSynthesis.speak(this.utterance);
      };
    }
  }

  stop(): void {
    if (!this.isSupported()) return;
    try { window.speechSynthesis.cancel(); } catch { /* already stopped */ }
    this.utterance = null;
  }

  isSpeaking(): boolean {
    if (!this.isSupported()) return false;
    return window.speechSynthesis.speaking;
  }

  private _pickVoice(voices: SpeechSynthesisVoice[], lang: SpeechLanguage): SpeechSynthesisVoice | null {
    // 1. Exact BCP-47 match (e.g. "fr-FR")
    const exact = voices.find((v) => v.lang === lang);
    if (exact) return exact;

    // 2. Language prefix match (e.g. "fr" for "fr-FR", "ar" for "ar-SA")
    const prefix = lang.split("-")[0];
    const prefix_match = voices.find((v) => v.lang.startsWith(prefix));
    if (prefix_match) return prefix_match;

    // 3. Browser default (null = browser picks automatically)
    return null;
  }
}

// ── Provider abstraction future hook ─────────────────────────────────────────
// To switch providers (e.g. OpenAI TTS), replace this function:
//
//   export function getTTSProvider(): TTSProvider {
//     if (process.env.NEXT_PUBLIC_TTS_PROVIDER === "openai")
//       return new OpenAITTSProvider();
//     return _default;
//   }

const _default = new WebSpeechTTSProvider();

export function getTTSProvider(): TTSProvider {
  return _default;
}
