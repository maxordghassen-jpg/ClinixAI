"use client";

import { motion } from "framer-motion";
import { Star, MapPin, Clock, User, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Doctor } from "@/types";

interface Props {
  doctor: Doctor;
  onBook?: (doctor: Doctor) => void;
  compact?: boolean;
}

const SPECIALTY_COLORS: Record<string, string> = {
  Cardiologist:    "bg-rose-50 text-rose-700 border-rose-100",
  Neurologist:     "bg-purple-50 text-purple-700 border-purple-100",
  Dermatologist:   "bg-amber-50 text-amber-700 border-amber-100",
  Pediatrician:    "bg-sky-50 text-sky-700 border-sky-100",
  Orthopedist:     "bg-teal-50 text-teal-700 border-teal-100",
  Ophthalmologist: "bg-indigo-50 text-indigo-700 border-indigo-100",
  default:         "bg-slate-50 text-slate-700 border-slate-200",
};

function SpecialtyBadge({ specialty }: { specialty: string }) {
  const cls = SPECIALTY_COLORS[specialty] ?? SPECIALTY_COLORS.default;
  return (
    <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full border", cls)}>
      {specialty}
    </span>
  );
}

function RatingStars({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          size={10}
          className={s <= Math.round(rating) ? "fill-amber-400 text-amber-400" : "text-slate-200 fill-slate-200"}
        />
      ))}
    </div>
  );
}

export default function DoctorCard({ doctor, onBook, compact = false }: Props) {
  if (compact) {
    return (
      <div className="flex items-center gap-3 p-3 rounded-xl border border-slate-100 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all cursor-pointer group">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center shrink-0 border border-indigo-100">
          <User size={16} className="text-indigo-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate">{doctor.name}</p>
          <p className="text-xs text-slate-500 truncate">{doctor.specialty}</p>
        </div>
        {doctor.next_available && (
          <div className="shrink-0 text-right">
            <p className="text-[10px] text-slate-400">Next</p>
            <p className="text-xs font-medium text-indigo-600">{doctor.next_available}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
      className="card p-5 flex flex-col gap-4"
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center shrink-0 border border-indigo-100 shadow-sm">
          <User size={20} className="text-indigo-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-800 truncate">{doctor.name}</p>
          <SpecialtyBadge specialty={doctor.specialty} />
        </div>
        {doctor.is_open_now !== undefined && (
          <span className={cn("text-[10px] font-semibold px-2 py-1 rounded-full shrink-0",
            doctor.is_open_now ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
          )}>
            {doctor.is_open_now ? "Open" : "Closed"}
          </span>
        )}
      </div>

      {/* Details */}
      <div className="space-y-1.5">
        {doctor.rating !== undefined && (
          <div className="flex items-center gap-2">
            <RatingStars rating={doctor.rating} />
            <span className="text-xs text-slate-600 font-medium">{doctor.rating.toFixed(1)}</span>
            {doctor.review_count && (
              <span className="text-xs text-slate-400">({doctor.review_count} reviews)</span>
            )}
          </div>
        )}
        {doctor.address && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <MapPin size={11} className="shrink-0 text-slate-400" />
            <span className="truncate">{doctor.address}</span>
          </div>
        )}
        {doctor.next_available && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock size={11} className="shrink-0 text-slate-400" />
            <span>Next available: <span className="font-medium text-indigo-600">{doctor.next_available}</span></span>
          </div>
        )}
      </div>

      {/* Book button */}
      {onBook && (
        <button
          onClick={() => onBook(doctor)}
          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors shadow-md shadow-indigo-200"
        >
          <Calendar size={14} />
          Book Appointment
        </button>
      )}
    </motion.div>
  );
}
