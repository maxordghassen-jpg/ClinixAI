"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  LayoutDashboard, CalendarDays, Users, Clock4,
  MessageSquareHeart, Stethoscope, Sparkles, ChevronRight,
  LogOut, Plus, Trash2, History,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/useAuthStore";
import { useDoctorChatStore } from "@/stores/doctor/useChatStore";
import { useIdentity } from "@/hooks/useIdentity";
import {
  listChatHistory, getChatHistorySession, deleteChatHistorySession,
} from "@/lib/api";
import type { ChatHistorySummary } from "@/types";

// ── Nav sections ──────────────────────────────────────────────────────────────

const sections = [
  {
    label: "Overview",
    items: [
      { href: "/doctor",              label: "Dashboard",    icon: LayoutDashboard    },
      { href: "/doctor/calendar",     label: "Calendar",     icon: CalendarDays       },
      { href: "/doctor/appointments", label: "Appointments", icon: Stethoscope        },
    ],
  },
  {
    label: "Management",
    items: [
      { href: "/doctor/availability", label: "Availability", icon: Clock4 },
      { href: "/doctor/patients",     label: "Patients",     icon: Users  },
    ],
  },
  {
    label: "Tools",
    items: [
      { href: "/doctor/chat", label: "AI Assistant", icon: MessageSquareHeart },
    ],
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const LANG_FLAG: Record<string, string> = { fr: "🇫🇷", ar: "🇸🇦", en: "🇬🇧" };

function langFlag(lang: string) {
  return LANG_FLAG[lang] ?? "🌐";
}

function dateGroup(iso: string): string {
  const d    = new Date(iso);
  const now  = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (diff === 0) return "Aujourd'hui";
  if (diff === 1) return "Hier";
  if (diff < 7)   return "Cette semaine";
  if (diff < 30)  return "Ce mois-ci";
  return "Plus ancien";
}

function groupByDate(list: ChatHistorySummary[]): [string, ChatHistorySummary[]][] {
  const order = ["Aujourd'hui", "Hier", "Cette semaine", "Ce mois-ci", "Plus ancien"];
  const map   = new Map<string, ChatHistorySummary[]>();
  for (const item of list) {
    const g = dateGroup(item.updated_at);
    if (!map.has(g)) map.set(g, []);
    map.get(g)!.push(item);
  }
  return order.filter((g) => map.has(g)).map((g) => [g, map.get(g)!]);
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function DoctorSidebar() {
  const pathname = usePathname();
  const router   = useRouter();
  const { user, clearAuth } = useAuthStore();
  const { doctorId }        = useIdentity();

  const {
    sessionId,
    historyList, loadingHistory,
    setHistoryList, setLoadingHistory,
    newSession, loadHistoryConversation,
  } = useDoctorChatStore();

  const mountedRef = useRef(true);
  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);

  useEffect(() => {
    if (!doctorId) return;
    let cancelled = false;
    setLoadingHistory(true);
    listChatHistory("doctor", doctorId)
      .then((list) => { if (!cancelled && mountedRef.current) setHistoryList(list); })
      .catch(() => {})
      .finally(() => { if (!cancelled && mountedRef.current) setLoadingHistory(false); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doctorId]);

  const isActive = (href: string) =>
    href === "/doctor" ? pathname === "/doctor" : pathname.startsWith(href);

  function handleLogout() {
    clearAuth();
    document.cookie = "clinix-token=; path=/; max-age=0";
    router.push("/login");
  }

  function handleNewSession() {
    newSession();
    if (pathname !== "/doctor/chat") router.push("/doctor/chat");
  }

  async function handleSelectHistory(item: ChatHistorySummary) {
    if (!doctorId) return;
    try {
      const full = await getChatHistorySession("doctor", doctorId, item.session_id);
      loadHistoryConversation(full.messages, full.session_id);
      if (pathname !== "/doctor/chat") router.push("/doctor/chat");
    } catch {}
  }

  async function handleDeleteHistory(e: React.MouseEvent, item: ChatHistorySummary) {
    e.stopPropagation();
    if (!doctorId) return;
    try {
      await deleteChatHistorySession("doctor", doctorId, item.session_id);
      setHistoryList(historyList.filter((h) => h.session_id !== item.session_id));
      if (sessionId === item.session_id) newSession();
    } catch {}
  }

  const initials = user?.name
    ? user.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
    : "DR";

  const groups = groupByDate(historyList);

  return (
    <aside className="fixed inset-y-0 left-0 z-40 w-64 flex flex-col bg-slate-900 overflow-y-auto">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-6 h-16 border-b border-white/5 shrink-0">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
          <Sparkles size={15} className="text-white" />
        </div>
        <span className="font-semibold text-white tracking-tight">ClinixAI</span>
        <span className="ml-auto text-[10px] font-medium text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded-md">
          Doctor
        </span>
      </div>

      {/* Nav */}
      <nav className="px-3 py-5 space-y-6">
        {sections.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href);
                return (
                  <Link key={href} href={href}>
                    <motion.div
                      whileHover={{ x: 2 }}
                      transition={{ duration: 0.15 }}
                      className={cn(
                        "group flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors",
                        active
                          ? "bg-violet-500/15 text-violet-300"
                          : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                      )}
                    >
                      <Icon
                        size={16}
                        className={cn(
                          "shrink-0 transition-colors",
                          active ? "text-violet-400" : "text-slate-500 group-hover:text-slate-300"
                        )}
                      />
                      {label}
                      {active && (
                        <ChevronRight size={12} className="ml-auto text-violet-400" />
                      )}
                    </motion.div>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Chat History section ── */}
      <div className="px-3 pb-3 border-t border-white/5 pt-4 flex-1">
        <button
          onClick={handleNewSession}
          className="w-full flex items-center gap-2 px-3 py-2 mb-3 rounded-xl text-sm font-medium bg-violet-500/15 text-violet-300 hover:bg-violet-500/25 transition-colors"
        >
          <Plus size={15} className="shrink-0" />
          Nouvelle conversation
        </button>

        <div className="flex items-center gap-2 px-3 mb-2">
          <History size={12} className="text-slate-500" />
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Historique des consultations
          </p>
        </div>

        {loadingHistory && (
          <p className="px-3 text-[11px] text-slate-600">Chargement…</p>
        )}

        {!loadingHistory && historyList.length === 0 && (
          <p className="px-3 text-[11px] text-slate-600">Aucune session</p>
        )}

        <div className="space-y-4">
          {groups.map(([group, items]) => (
            <div key={group}>
              <p className="px-3 mb-1 text-[10px] font-medium text-slate-600">{group}</p>
              <div className="space-y-0.5">
                {items.map((item) => {
                  const isSelected = sessionId === item.session_id;
                  return (
                    <div
                      key={item.session_id}
                      onClick={() => handleSelectHistory(item)}
                      className={cn(
                        "group relative flex items-start gap-2 px-3 py-2 rounded-xl cursor-pointer transition-colors",
                        isSelected
                          ? "bg-violet-500/15"
                          : "hover:bg-white/5"
                      )}
                    >
                      <span className="text-xs shrink-0 mt-0.5">{langFlag(item.language)}</span>
                      <div className="flex-1 min-w-0">
                        <p
                          className={cn(
                            "text-xs font-medium truncate",
                            isSelected ? "text-violet-300" : "text-slate-300"
                          )}
                          style={{ maxWidth: "calc(100% - 20px)" }}
                        >
                          {item.title || "Session"}
                        </p>
                        <p className="text-[10px] text-slate-600 mt-0.5">
                          {new Date(item.updated_at).toLocaleDateString("fr-FR", {
                            day: "numeric", month: "short",
                          })}
                        </p>
                      </div>
                      <button
                        onClick={(e) => handleDeleteHistory(e, item)}
                        className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 p-1 rounded-lg transition-all hover:text-rose-400 text-slate-500"
                        title="Supprimer"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Profile + logout */}
      <div className="px-3 pb-4 border-t border-white/5 pt-3 space-y-1 shrink-0">
        <div className="flex items-center gap-3 px-3 py-2 rounded-xl">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 flex items-center justify-center text-white text-xs font-semibold shrink-0">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-slate-200 truncate">{user?.name ?? "Doctor"}</p>
            <p className="text-xs text-slate-500 truncate">{user?.email ?? ""}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm font-medium text-slate-400 hover:bg-white/5 hover:text-rose-400 transition-colors"
        >
          <LogOut size={15} className="shrink-0" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
