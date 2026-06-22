"use client";

import { useEffect } from "react";
import TopBar from "@/components/layout/TopBar";
import ChatPanel from "@/components/chat/ChatPanel";
import { useDoctorChatStore } from "@/stores/doctor/useChatStore";
import { useIdentity } from "@/hooks/useIdentity";
import { useAuthStore } from "@/stores/useAuthStore";
import { doctorChat, saveChatHistory, listChatHistory } from "@/lib/api";

function detectLanguage(text: string): string {
  if (/[؀-ۿ]/.test(text)) return "ar";
  if (/[àâäéèêëîïôùûüÿçœæ]/i.test(text) ||
      /\b(je|tu|il|nous|vous|le|la|les|des|du|un|une|et|en|de|à|au|pour|dans|mon|ma|mes)\b/i.test(text))
    return "fr";
  return "en";
}

export default function DoctorChatPage() {
  const { doctorId } = useIdentity();
  // Fallback: read doctor_id directly from the auth store
  const { user } = useAuthStore();
  const resolvedDoctorId = doctorId ?? user?.doctor_id ?? null;

  const {
    messages, isLoading, isOpen, sessionId, isReadOnly,
    addMessage, setLoading, togglePanel, newSession, setHistoryList,
  } = useDoctorChatStore();

  // Initialise session on first mount
  useEffect(() => {
    if (!sessionId) newSession();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSend(text: string) {
    if (isReadOnly || !sessionId) return;
    const ts = new Date().toLocaleTimeString();
    const userMsg = { role: "user" as const, content: text, timestamp: ts };
    addMessage(userMsg);
    setLoading(true);

    let assistantMsg = { role: "assistant" as const, content: "", timestamp: "" };
    try {
      const res = await doctorChat({
        message:    text,
        session_id: sessionId,
        doctor_id:  resolvedDoctorId || undefined,
      });
      assistantMsg = {
        role: "assistant",
        content: res.response ?? "(no response)",
        timestamp: new Date().toLocaleTimeString(),
      };
      addMessage(assistantMsg);
    } catch (err) {
      assistantMsg = {
        role: "assistant",
        content: err instanceof Error ? err.message : "Something went wrong",
        timestamp: new Date().toLocaleTimeString(),
      };
      addMessage(assistantMsg);
    } finally {
      setLoading(false);
    }

    // Save and immediately refresh the sidebar history list
    if (resolvedDoctorId && sessionId) {
      const allMessages = [...messages, userMsg, assistantMsg];
      saveChatHistory({
        user_id:    resolvedDoctorId,
        user_role:  "doctor",
        session_id: sessionId,
        messages:   allMessages,
        language:   detectLanguage(text),
      })
        .then(() =>
          listChatHistory("doctor", resolvedDoctorId)
            .then(setHistoryList)
            .catch(() => {})
        )
        .catch((err) =>
          console.error("[ChatHistory] save failed:", err)
        );
    } else {
      console.warn(
        "[ChatHistory] save skipped — resolvedDoctorId=%s sessionId=%s",
        resolvedDoctorId,
        sessionId,
      );
    }
  }

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="AI Doctor Assistant" subtitle="Ask about your schedule, patients, and availability" />

      {/* Read-only banner */}
      {isReadOnly && (
        <div className="mx-6 mt-4 px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800 flex items-center gap-2">
          <span>📁</span>
          <span>
            Historique de session — cliquez sur{" "}
            <strong>+ Nouvelle conversation</strong> dans la barre latérale pour continuer.
          </span>
        </div>
      )}

      <div className="flex-1 p-6 flex items-start justify-center">
        <div className="w-full max-w-2xl">
          <ChatPanel
            title="Doctor AI Assistant"
            placeholder="Show tomorrow's appointments, block Friday morning…"
            messages={messages}
            isLoading={isLoading}
            isOpen={isOpen}
            onToggle={togglePanel}
            onSend={handleSend}
            onClear={newSession}
          />
        </div>
      </div>
    </div>
  );
}
