"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Message } from "@/types";

export default function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0 mt-0.5 shadow-md shadow-indigo-200">
          <Sparkles size={12} className="text-white" />
        </div>
      )}

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[78%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-indigo-600 text-white rounded-tr-sm shadow-md shadow-indigo-200"
            : "bg-white border border-slate-200 text-slate-800 rounded-tl-sm shadow-sm"
        )}
      >
        <p className="whitespace-pre-wrap">{msg.content}</p>
        <p className={cn("text-[10px] mt-1", isUser ? "text-indigo-200 text-right" : "text-slate-400")}>
          {msg.timestamp}
        </p>
      </div>
    </motion.div>
  );
}
