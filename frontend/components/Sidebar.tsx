"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/patient",       label: "Patient Chat",    icon: "💬" },
  { href: "/doctor",        label: "Doctor Chat",     icon: "🩺" },
  { href: "/appointments",  label: "Appointments",    icon: "📅" },
  { href: "/availability",  label: "Availability",    icon: "🕐" },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-52 shrink-0 bg-white border-r border-gray-200 flex flex-col py-6 px-3 gap-1">
      <div className="px-3 mb-4">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          ClinixAI — Dev
        </span>
      </div>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            path.startsWith(l.href)
              ? "bg-blue-50 text-blue-700"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <span>{l.icon}</span>
          {l.label}
        </Link>
      ))}
    </aside>
  );
}
