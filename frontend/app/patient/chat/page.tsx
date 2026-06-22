"use client";

import { useEffect } from "react";
import TopBar from "@/components/layout/TopBar";
import ChatPanel from "@/components/chat/ChatPanel";
import { usePatientChatStore } from "@/stores/patient/useChatStore";
import { useOrchestrationStore } from "@/stores/useOrchestrationStore";
import { useAIOrchestration } from "@/hooks/useAIOrchestration";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useIdentity } from "@/hooks/useIdentity";
import { useAuthStore } from "@/stores/useAuthStore";
import { patientChat, saveChatHistory, listChatHistory } from "@/lib/api";

function detectLanguage(text: string): string {
  if (/[؀-ۿ]/.test(text)) return "ar";
  if (/[àâäéèêëîïôùûüÿçœæ]/i.test(text) ||
      /\b(je|tu|il|nous|vous|le|la|les|des|du|un|une|et|en|de|à|au|pour|dans|mon|ma|mes)\b/i.test(text))
    return "fr";
  return "en";
}

export default function PatientChatPage() {
  const { patientId } = useIdentity();
  // Fallback: read patient_profile_id directly from the auth store in case
  // useIdentity resolves to null (e.g. stale store shape from an older login)
  const { user } = useAuthStore();
  const resolvedPatientId = patientId ?? user?.patient_profile_id ?? null;

  const {
    messages, isLoading, isOpen, sessionId, isReadOnly,
    addMessage, setLoading, togglePanel, newSession, setHistoryList,
  } = usePatientChatStore();
  const { handleAIResponse } = useAIOrchestration();
  const { userLocation } = useOrchestrationStore();
  useGeolocation();

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
      const payload = {
        message:    text,
        session_id: sessionId,
        patient_id: resolvedPatientId ?? undefined,
        latitude:   userLocation?.lat,
        longitude:  userLocation?.lng,
      };
      console.log("PATIENT_CHAT_PAYLOAD", payload);
      const res = await patientChat(payload);
      assistantMsg = {
        role: "assistant",
        content: res.response ?? "(no response)",
        timestamp: new Date().toLocaleTimeString(),
      };
      addMessage(assistantMsg);
      handleAIResponse(res as Parameters<typeof handleAIResponse>[0]);
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
    if (resolvedPatientId && sessionId) {
      const allMessages = [...messages, userMsg, assistantMsg];
      saveChatHistory({
        user_id:    resolvedPatientId,
        user_role:  "patient",
        session_id: sessionId,
        messages:   allMessages,
        language:   detectLanguage(text),
      })
        .then(() =>
          listChatHistory("patient", resolvedPatientId)
            .then(setHistoryList)
            .catch(() => {})
        )
        .catch((err) =>
          console.error("[ChatHistory] save failed:", err)
        );
    } else {
      console.warn(
        "[ChatHistory] save skipped — resolvedPatientId=%s sessionId=%s",
        resolvedPatientId,
        sessionId,
      );
    }
  }

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="AI Health Assistant" subtitle="Ask about appointments, doctors, and more" />

      {/* Read-only banner */}
      {isReadOnly && (
        <div className="mx-6 mt-4 px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800 flex items-center gap-2">
          <span>📁</span>
          <span>
            Conversation archivée — cliquez sur{" "}
            <strong>+ Nouvelle conversation</strong> dans la barre latérale pour continuer.
          </span>
        </div>
      )}

      <div className="flex-1 p-6 flex items-start justify-center">
        <div className="w-full max-w-2xl">
          <ChatPanel
            title="Patient AI Assistant"
            placeholder="Book an appointment, find a specialist, check my schedule…"
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
