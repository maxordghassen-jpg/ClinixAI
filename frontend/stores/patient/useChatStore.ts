import { create } from "zustand";
import type { ChatHistorySummary, Message } from "@/types";

interface PatientChatState {
  messages:       Message[];
  isLoading:      boolean;
  isOpen:         boolean;
  sessionId:      string | null;
  isReadOnly:     boolean;
  historyList:    ChatHistorySummary[];
  loadingHistory: boolean;

  addMessage:             (msg: Message) => void;
  setLoading:             (v: boolean) => void;
  setOpen:                (v: boolean) => void;
  togglePanel:            () => void;
  clearMessages:          () => void;
  setSessionId:           (id: string) => void;
  setReadOnly:            (v: boolean) => void;
  setHistoryList:         (list: ChatHistorySummary[]) => void;
  setLoadingHistory:      (v: boolean) => void;
  newSession:             () => void;
  loadHistoryConversation:(messages: Message[], sessionId: string) => void;
}

function generateSessionId(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export const usePatientChatStore = create<PatientChatState>()((set) => ({
  messages:       [],
  isLoading:      false,
  isOpen:         true,
  sessionId:      null,
  isReadOnly:     false,
  historyList:    [],
  loadingHistory: false,

  addMessage:        (msg)  => set((s) => ({ messages: [...s.messages, msg] })),
  setLoading:        (v)    => set({ isLoading: v }),
  setOpen:           (v)    => set({ isOpen: v }),
  togglePanel:       ()     => set((s) => ({ isOpen: !s.isOpen })),
  clearMessages:     ()     => set({ messages: [] }),
  setSessionId:      (id)   => set({ sessionId: id }),
  setReadOnly:       (v)    => set({ isReadOnly: v }),
  setHistoryList:    (list) => set({ historyList: list }),
  setLoadingHistory: (v)    => set({ loadingHistory: v }),

  newSession: () =>
    set({ messages: [], sessionId: generateSessionId(), isReadOnly: false }),

  loadHistoryConversation: (messages, sessionId) =>
    set({ messages, sessionId, isReadOnly: true, isOpen: true }),
}));
