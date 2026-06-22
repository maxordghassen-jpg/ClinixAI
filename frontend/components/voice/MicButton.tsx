"use client";

import { Mic, MicOff, StopCircle } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { VoiceState } from "@/hooks/useVoice";

interface Props {
  state:     VoiceState;
  onToggle:  () => void;
  disabled?: boolean;
  className?: string;
}

export default function MicButton({ state, onToggle, disabled, className }: Props) {
  const ariaLabel =
    state === "listening" ? "Stop recording"  :
    state === "speaking"  ? "Stop speaking"   :
    "Start voice input";

  return (
    <motion.button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      aria-label={ariaLabel}
      title={ariaLabel}
      whileTap={{ scale: 0.88 }}
      className={cn(
        "relative w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-colors select-none",
        state === "listening"
          ? "bg-rose-500 hover:bg-rose-600 shadow-md shadow-rose-200/60"
          : state === "speaking"
          ? "bg-violet-600 hover:bg-violet-700 shadow-md shadow-violet-200/60"
          : "bg-slate-100 hover:bg-slate-200 border border-slate-200",
        disabled && "opacity-40 cursor-not-allowed pointer-events-none",
        className,
      )}
    >
      {/* Pulse ring — listening only */}
      {state === "listening" && (
        <>
          <motion.span
            aria-hidden
            className="absolute inset-0 rounded-xl bg-rose-400"
            animate={{ scale: [1, 1.55, 1], opacity: [0.55, 0, 0.55] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.span
            aria-hidden
            className="absolute inset-0 rounded-xl bg-rose-300"
            animate={{ scale: [1, 1.85, 1], opacity: [0.35, 0, 0.35] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
          />
        </>
      )}

      {/* Icon */}
      <span className="relative z-10">
        {state === "listening" ? (
          <MicOff size={14} className="text-white" />
        ) : state === "speaking" ? (
          <StopCircle size={14} className="text-white" />
        ) : (
          <Mic size={14} className="text-slate-500" />
        )}
      </span>
    </motion.button>
  );
}
