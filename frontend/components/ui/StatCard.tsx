"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: number | string;
  change?: string;
  trend?: "up" | "down" | "neutral";
  icon: LucideIcon;
  color?: "indigo" | "teal" | "rose" | "amber" | "violet";
  suffix?: string;
}

const colorMap = {
  indigo: {
    icon: "bg-indigo-100 text-indigo-600",
    trend: "text-indigo-600",
    glow: "shadow-indigo-100",
  },
  teal: {
    icon: "bg-teal-100 text-teal-600",
    trend: "text-teal-600",
    glow: "shadow-teal-100",
  },
  rose: {
    icon: "bg-rose-100 text-rose-600",
    trend: "text-rose-600",
    glow: "shadow-rose-100",
  },
  amber: {
    icon: "bg-amber-100 text-amber-600",
    trend: "text-amber-600",
    glow: "shadow-amber-100",
  },
  violet: {
    icon: "bg-violet-100 text-violet-600",
    trend: "text-violet-600",
    glow: "shadow-violet-100",
  },
};

const TrendIcon = ({ trend }: { trend: "up" | "down" | "neutral" }) => {
  if (trend === "up") return <TrendingUp size={12} className="text-emerald-500" />;
  if (trend === "down") return <TrendingDown size={12} className="text-red-400" />;
  return <Minus size={12} className="text-slate-400" />;
};

export default function StatCard({ label, value, change, trend = "neutral", icon: Icon, color = "indigo", suffix }: Props) {
  const c = colorMap[color];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      whileHover={{ y: -2 }}
      className={cn("card p-5 flex items-start gap-4", c.glow)}
    >
      <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center shrink-0", c.icon)}>
        <Icon size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide truncate">{label}</p>
        <p className="text-2xl font-bold text-slate-800 mt-0.5 leading-none">
          {value}
          {suffix && <span className="text-base font-normal text-slate-500 ml-0.5">{suffix}</span>}
        </p>
        {change && (
          <div className="flex items-center gap-1 mt-1.5">
            <TrendIcon trend={trend} />
            <span className={cn("text-[11px] font-medium",
              trend === "up" ? "text-emerald-600" :
              trend === "down" ? "text-red-500" : "text-slate-400"
            )}>
              {change}
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
