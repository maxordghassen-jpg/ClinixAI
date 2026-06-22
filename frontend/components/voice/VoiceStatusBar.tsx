"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Volume2, X } from "lucide-react";
import type { VoiceState } from "@/hooks/useVoice";

interface Props {
  state:      VoiceState;
  transcript: string;
  onStop:     () => void;
}

// Animated bar segment — one column in the waveform
function WaveBar({ delay, color, maxH }: { delay: number; color: string; maxH: string }) {
  return (
    <motion.span
      aria-hidden
      className={`w-[3px] rounded-full ${color}`}
      animate={{ height: ["3px", maxH, "3px"] }}
      transition={{
        duration:   0.65,
        repeat:     Infinity,
        ease:       "easeInOut",
        delay,
      }}
    />
  );
}

export default function VoiceStatusBar({ state, transcript, onStop }: Props) {
  return (
    <AnimatePresence>
      {state !== "idle" && (
        <motion.div
          key={state}
          initial={{ opacity: 0, height: 0, marginBottom: 0 }}
          animate={{ opacity: 1, height: "auto", marginBottom: 8 }}
          exit={{ opacity: 0, height: 0, marginBottom: 0 }}
          transition={{ duration: 0.18 }}
          className="overflow-hidden"
        >
          {state === "listening" ? (
            /* ── Recording / transcribing ──────────────────────────── */
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-rose-50 border border-rose-100">
              {/* Waveform */}
              <div className="flex items-center gap-[3px] shrink-0">
                {[0, 0.12, 0.24, 0.36].map((d, i) => (
                  <WaveBar key={i} delay={d} color="bg-rose-400" maxH="14px" />
                ))}
              </div>

              <span className="flex-1 min-w-0 truncate text-xs font-medium text-rose-700">
                {transcript || "Listening…"}
              </span>

              <button
                type="button"
                onClick={onStop}
                aria-label="Cancel recording"
                className="p-0.5 rounded-md hover:bg-rose-100 transition-colors shrink-0"
              >
                <X size={11} className="text-rose-400" />
              </button>
            </div>
          ) : (
            /* ── Speaking ──────────────────────────────────────────── */
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-violet-50 border border-violet-100">
              <Volume2 size={12} className="text-violet-400 shrink-0" />

              {/* Waveform */}
              <div className="flex items-center gap-[3px] shrink-0">
                {[0, 0.1, 0.2, 0.3, 0.4].map((d, i) => (
                  <WaveBar key={i} delay={d} color="bg-violet-400" maxH="12px" />
                ))}
              </div>

              <span className="flex-1 text-xs font-medium text-violet-700">
                Speaking…
              </span>

              <button
                type="button"
                onClick={onStop}
                aria-label="Stop speaking"
                className="p-0.5 rounded-md hover:bg-violet-100 transition-colors shrink-0"
              >
                <X size={11} className="text-violet-400" />
              </button>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
