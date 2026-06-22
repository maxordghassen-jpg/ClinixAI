"use client";

import { useState } from "react";
import { Play, Search } from "lucide-react";
import { motion } from "framer-motion";
import { EvalScenario, CATEGORY_LABELS } from "@/types/eval";

interface Props {
  scenarios:  EvalScenario[];
  onRun:      (id: string) => Promise<void>;
  running?:   string | null;
}

const CATEGORIES = [
  "all", "workflow", "memory", "safety", "hallucination",
  "multilingual", "recommendation", "doctor", "voice",
];

const CATEGORY_COLORS: Record<string, string> = {
  workflow:       "bg-violet-100 text-violet-700",
  memory:         "bg-blue-100 text-blue-700",
  safety:         "bg-red-100 text-red-700",
  hallucination:  "bg-amber-100 text-amber-700",
  multilingual:   "bg-teal-100 text-teal-700",
  recommendation: "bg-emerald-100 text-emerald-700",
  doctor:         "bg-indigo-100 text-indigo-700",
  voice:          "bg-pink-100 text-pink-700",
};

export default function ScenarioRunner({ scenarios, onRun, running }: Props) {
  const [category, setCategory] = useState("all");
  const [search,   setSearch]   = useState("");

  const filtered = scenarios.filter(s => {
    const matchCat    = category === "all" || s.category === category;
    const matchSearch = !search
      || s.name.toLowerCase().includes(search.toLowerCase())
      || s.id.toLowerCase().includes(search.toLowerCase())
      || s.user_message.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  return (
    <div className="flex flex-col gap-5">

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search scenarios…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-white border border-slate-200 rounded-xl pl-8 pr-3 py-2 text-sm
                       text-slate-700 placeholder-slate-400
                       focus:outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100
                       w-52 transition-all"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                category === cat
                  ? "bg-violet-600 text-white shadow-sm shadow-violet-200"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
              }`}
            >
              {cat === "all" ? "All" : CATEGORY_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>

        <span className="text-xs text-slate-400 ml-auto">
          {filtered.length} scenario{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Cards grid */}
      {filtered.length === 0 ? (
        <div className="py-16 text-center bg-white border border-slate-200 rounded-2xl">
          <p className="text-sm text-slate-400">No scenarios match your filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((s, i) => {
            const isRunning = running === s.id;
            const catColor  = CATEGORY_COLORS[s.category] ?? "bg-slate-100 text-slate-600";

            return (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, delay: Math.min(i * 0.035, 0.35) }}
                whileHover={{ y: -2 }}
                className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col gap-3
                           hover:border-slate-300 hover:shadow-md transition-all"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-[11px] font-mono font-semibold text-violet-500">
                      {s.id}
                    </span>
                    <span className="text-sm font-semibold text-slate-800 leading-snug">
                      {s.name}
                    </span>
                  </div>
                  <span className={`shrink-0 px-2.5 py-1 rounded-lg text-xs font-medium capitalize ${catColor}`}>
                    {CATEGORY_LABELS[s.category] ?? s.category}
                  </span>
                </div>

                {/* Description */}
                <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">
                  {s.description}
                </p>

                {/* Meta */}
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="uppercase font-medium">{s.language.slice(0, 2)}</span>
                  <span className="text-slate-200">·</span>
                  <span className="capitalize">{s.role}</span>
                  {s.tags.length > 0 && (
                    <>
                      <span className="text-slate-200">·</span>
                      <span className="truncate">{s.tags.slice(0, 2).join(", ")}</span>
                    </>
                  )}
                </div>

                {/* Message preview */}
                <blockquote
                  className="text-xs text-slate-500 italic border-l-2 border-violet-200
                             pl-3 py-1.5 pr-2 leading-relaxed line-clamp-2
                             bg-slate-50/80 rounded-r-lg"
                >
                  &ldquo;{s.user_message}&rdquo;
                </blockquote>

                {/* Run button */}
                <button
                  onClick={() => onRun(s.id)}
                  disabled={!!running}
                  className={`mt-auto flex items-center justify-center gap-2 py-2.5 px-4
                              rounded-xl text-xs font-semibold transition-all ${
                    isRunning
                      ? "bg-violet-100 text-violet-500 cursor-wait"
                      : running
                        ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                        : "bg-violet-600 hover:bg-violet-700 text-white shadow-sm shadow-violet-200"
                  }`}
                >
                  {isRunning ? (
                    <>
                      <span className="w-3 h-3 border-2 border-violet-400 border-t-transparent
                                       rounded-full animate-spin" />
                      Evaluating…
                    </>
                  ) : (
                    <><Play size={12} /> Run Scenario</>
                  )}
                </button>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
