"use client";

import { useState } from "react";
import { Clock, Plus, Trash2, Save } from "lucide-react";
import TopBar from "@/components/layout/TopBar";
import { cn } from "@/lib/utils";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface Slot { start: string; end: string }
type Schedule = Record<string, Slot[]>;

const DEFAULT_SLOTS: Slot[] = [{ start: "09:00", end: "17:00" }];

export default function DoctorAvailabilityPage() {
  const [schedule, setSchedule] = useState<Schedule>(() =>
    Object.fromEntries(
      DAYS.map((d) => [d, d === "Saturday" || d === "Sunday" ? [] : [...DEFAULT_SLOTS]])
    )
  );
  const [saved, setSaved] = useState(false);
  const [duration, setDuration] = useState(30);

  function addSlot(day: string) {
    setSchedule((prev) => ({
      ...prev,
      [day]: [...prev[day], { start: "09:00", end: "17:00" }],
    }));
    setSaved(false);
  }

  function removeSlot(day: string, idx: number) {
    setSchedule((prev) => ({
      ...prev,
      [day]: prev[day].filter((_, i) => i !== idx),
    }));
    setSaved(false);
  }

  function updateSlot(day: string, idx: number, field: "start" | "end", value: string) {
    setSchedule((prev) => ({
      ...prev,
      [day]: prev[day].map((s, i) => (i === idx ? { ...s, [field]: value } : s)),
    }));
    setSaved(false);
  }

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  const totalSlots = Object.values(schedule).flat().length;
  const activeDays = Object.entries(schedule).filter(([, slots]) => slots.length > 0).length;

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="Availability" subtitle="Set your weekly working hours" />

      <div className="flex-1 p-6 space-y-6 max-w-3xl">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Active Days",        value: activeDays },
            { label: "Total Time Blocks",  value: totalSlots },
            { label: "Slot Duration (min)", value: duration  },
          ].map(({ label, value }) => (
            <div key={label} className="card p-4 text-center">
              <p className="text-xl font-bold text-slate-800">{value}</p>
              <p className="text-xs text-slate-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* Duration */}
        <div className="card p-5 flex items-center gap-4">
          <Clock size={16} className="text-slate-400 shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-700">Consultation Duration</p>
            <p className="text-xs text-slate-400">How long each appointment slot lasts</p>
          </div>
          <div className="flex items-center gap-2">
            {[15, 20, 30, 45, 60].map((d) => (
              <button
                key={d}
                onClick={() => { setDuration(d); setSaved(false); }}
                className={cn(
                  "w-10 h-9 text-xs font-semibold rounded-xl border transition-colors",
                  duration === d
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
                )}
              >
                {d}m
              </button>
            ))}
          </div>
        </div>

        {/* Weekly schedule */}
        <div className="space-y-3">
          {DAYS.map((day) => {
            const slots = schedule[day];
            const isOff = slots.length === 0;
            return (
              <div key={day} className={cn("card p-4", isOff && "opacity-60")}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <button
                      onClick={() => {
                        if (isOff) addSlot(day);
                        else setSchedule((prev) => ({ ...prev, [day]: [] }));
                        setSaved(false);
                      }}
                      className={cn(
                        "w-9 h-5 rounded-full transition-colors relative",
                        isOff ? "bg-slate-200" : "bg-indigo-500"
                      )}
                    >
                      <span className={cn(
                        "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all",
                        isOff ? "left-0.5" : "left-4"
                      )} />
                    </button>
                    <span className="text-sm font-semibold text-slate-700">{day}</span>
                    {isOff && <span className="text-xs text-slate-400">Day off</span>}
                  </div>
                  {!isOff && (
                    <button
                      onClick={() => addSlot(day)}
                      className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      <Plus size={12} /> Add block
                    </button>
                  )}
                </div>

                {!isOff && (
                  <div className="space-y-2">
                    {slots.map((slot, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="time"
                          value={slot.start}
                          onChange={(e) => updateSlot(day, idx, "start", e.target.value)}
                          className="input-base text-xs py-1.5 w-28"
                        />
                        <span className="text-slate-400 text-xs">to</span>
                        <input
                          type="time"
                          value={slot.end}
                          onChange={(e) => updateSlot(day, idx, "end", e.target.value)}
                          className="input-base text-xs py-1.5 w-28"
                        />
                        <button
                          onClick={() => removeSlot(day, idx)}
                          className="ml-auto p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          className={cn(
            "flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all shadow-sm",
            saved
              ? "bg-emerald-600 text-white shadow-emerald-200"
              : "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-200"
          )}
        >
          <Save size={14} />
          {saved ? "Saved!" : "Save Availability"}
        </button>
      </div>
    </div>
  );
}
