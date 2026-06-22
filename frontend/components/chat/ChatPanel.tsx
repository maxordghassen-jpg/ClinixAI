"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Trash2, Sparkles, X, ChevronDown, Settings2, AlertCircle } from "lucide-react";
import ChatMessage from "./ChatMessage";
import TypingIndicator from "./TypingIndicator";
import MicButton from "@/components/voice/MicButton";
import VoiceStatusBar from "@/components/voice/VoiceStatusBar";
import { cn } from "@/lib/utils";
import type { Message } from "@/types";
import type { VoiceState } from "@/hooks/useVoice";

// ── Voice prop surface ────────────────────────────────────────────────────────

export interface VoicePanelProps {
  voiceState:   VoiceState;
  transcript:   string;
  isSupported:  boolean;
  error:        string | null;
  onToggle:     () => void;
  onStop:       () => void;
}

// ── Panel props ───────────────────────────────────────────────────────────────

interface Props {
  title:        string;
  placeholder?: string;
  messages:     Message[];
  isLoading:    boolean;
  isOpen:       boolean;
  onToggle:     () => void;
  onSend:       (text: string) => Promise<void>;
  onClear:      () => void;
  voice?:       VoicePanelProps;
  configSlot?:  React.ReactNode;
}

const QUICK_PROMPTS_PATIENT = [
  "Book an appointment",
  "Find a cardiologist nearby",
  "My upcoming appointments",
];

const QUICK_PROMPTS_DOCTOR = [
  "Show tomorrow's appointments",
  "Block Friday morning",
  "My availability this week",
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChatPanel({
  title,
  placeholder = "Ask me anything…",
  messages,
  isLoading,
  isOpen,
  onToggle,
  onSend,
  onClear,
  voice,
  configSlot,
}: Props) {
  const [input,      setInput]      = useState("");
  const [showConfig, setShowConfig] = useState(false);
  const [mounted,    setMounted]    = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);

  const quickPrompts = title.toLowerCase().includes("doctor")
    ? QUICK_PROMPTS_DOCTOR
    : QUICK_PROMPTS_PATIENT;

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  async function handleSubmit(e?: { preventDefault?(): void }) {
    e?.preventDefault?.();
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    await onSend(text);
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  // Voice error auto-dismisses after 5 s
  const [voiceErrorVisible, setVoiceErrorVisible] = useState(false);
  useEffect(() => {
    if (voice?.error) {
      setVoiceErrorVisible(true);
      const t = setTimeout(() => setVoiceErrorVisible(false), 5000);
      return () => clearTimeout(t);
    }
  }, [voice?.error]);

  return (
    <div className={cn(
      "flex flex-col bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden",
      !isOpen && "h-14",
    )}>
      {/* ── Header ── */}
      <div
        className="flex items-center gap-2.5 px-4 h-14 border-b border-slate-100 cursor-pointer shrink-0 hover:bg-slate-50/60 transition-colors"
        onClick={onToggle}
      >
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-md shadow-indigo-200">
          <Sparkles size={13} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800">{title}</p>
          <p className="text-[10px] text-slate-400 flex items-center gap-1">
            AI-powered assistant
            {/* Voice availability badge */}
            {mounted && voice?.isSupported && (
              <span className="text-[9px] font-medium text-violet-500 bg-violet-50 px-1.5 py-px rounded-full border border-violet-100">
                Voice
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1">
          {configSlot && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowConfig(!showConfig); }}
              className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <Settings2 size={13} className="text-slate-400" />
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onClear(); }}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <Trash2 size={13} className="text-slate-400" />
          </button>
          <button className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors">
            {isOpen
              ? <X size={14} className="text-slate-400" />
              : <ChevronDown size={14} className="text-slate-400" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col flex-1 min-h-0"
          >
            {/* Config drawer */}
            {configSlot && showConfig && (
              <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 text-sm">
                {configSlot}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[240px]">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-4 pt-4">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center">
                    <Sparkles size={18} className="text-indigo-500" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-slate-700">AI Assistant ready</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {mounted && voice?.isSupported
                        ? "Type or tap the mic to start"
                        : "Ask anything or try a suggestion"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {quickPrompts.map((q) => (
                      <button
                        key={q}
                        onClick={() => { setInput(q); inputRef.current?.focus(); }}
                        className="text-xs px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-100 transition-colors font-medium"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg, i) => <ChatMessage key={i} msg={msg} />)}
              {isLoading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>

            {/* Input area */}
            <div className="p-3 border-t border-slate-100">
              {/* Voice status bar (listening / speaking) */}
              {voice && (
                <VoiceStatusBar
                  state={voice.voiceState}
                  transcript={voice.transcript}
                  onStop={voice.onStop}
                />
              )}

              {/* Voice error toast */}
              <AnimatePresence>
                {voice && voiceErrorVisible && voice.error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                    animate={{ opacity: 1, height: "auto", marginBottom: 8 }}
                    exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-50 border border-amber-100 overflow-hidden"
                  >
                    <AlertCircle size={12} className="text-amber-500 shrink-0" />
                    <span className="text-xs text-amber-700 flex-1">{voice.error}</span>
                    <button
                      type="button"
                      onClick={() => setVoiceErrorVisible(false)}
                      className="p-0.5 hover:bg-amber-100 rounded transition-colors"
                    >
                      <X size={10} className="text-amber-400" />
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Text input row */}
              <form onSubmit={handleSubmit} className="flex gap-2 items-end">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    voice?.voiceState === "listening"
                      ? "Listening…"
                      : voice?.voiceState === "speaking"
                      ? "Speaking…"
                      : placeholder
                  }
                  rows={1}
                  disabled={isLoading || voice?.voiceState === "listening"}
                  className={cn(
                    "flex-1 resize-none bg-slate-50 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 transition-all min-h-[40px] max-h-24",
                    voice?.voiceState === "listening"
                      ? "border-rose-200 bg-rose-50/40 focus:border-rose-300 focus:ring-rose-100 placeholder:text-rose-300 cursor-not-allowed opacity-70"
                      : voice?.voiceState === "speaking"
                      ? "border-violet-200 bg-violet-50/40 focus:border-violet-300 focus:ring-violet-100 placeholder:text-violet-300"
                      : "border-slate-200 focus:border-indigo-300 focus:ring-indigo-100 disabled:opacity-50",
                  )}
                  style={{ lineHeight: "1.4" }}
                />

                {/* Mic button — rendered when supported */}
                {mounted && voice?.isSupported && (
                  <MicButton
                    state={voice.voiceState}
                    onToggle={voice.onToggle}
                    disabled={isLoading}
                  />
                )}

                {/* Send button */}
                <button
                  type="submit"
                  disabled={isLoading || !input.trim() || voice?.voiceState === "listening"}
                  className="w-9 h-9 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 flex items-center justify-center shrink-0 transition-colors shadow-md shadow-indigo-200"
                >
                  <Send size={14} className="text-white" />
                </button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
