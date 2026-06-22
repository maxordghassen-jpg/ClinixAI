"use client";

import { Bell, Search } from "lucide-react";

interface Props {
  title: string;
  subtitle?: string;
}

export default function TopBar({ title, subtitle }: Props) {
  return (
    <header className="sticky top-0 z-30 h-14 flex items-center gap-4 bg-white/80 backdrop-blur-md border-b border-slate-200 px-6">
      {/* Page title */}
      <div className="flex-1 min-w-0">
        <h1 className="text-sm font-semibold text-slate-900 truncate">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500 truncate">{subtitle}</p>}
      </div>

      {/* Search */}
      <div className="relative hidden md:block">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
        />
        <input
          type="text"
          placeholder="Search…"
          className="pl-8 pr-4 py-1.5 text-sm bg-slate-100 border border-transparent rounded-lg focus:outline-none focus:border-indigo-300 focus:bg-white transition-colors w-48"
        />
      </div>

      {/* Notifications */}
      <button className="relative p-2 rounded-lg hover:bg-slate-100 transition-colors">
        <Bell size={16} className="text-slate-600" />
        <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500" />
      </button>
    </header>
  );
}
