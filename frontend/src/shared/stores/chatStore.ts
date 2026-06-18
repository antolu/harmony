import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SourceItem, StepEntry } from "@/shared/hooks/useChat";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: SourceItem[];
  steps?: StepEntry[];
}

interface ChatState {
  messages: ChatMessage[];
  sidebarOpen: boolean;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  sidebarOpen: false,
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));

interface ConversationState {
  currentConversationId: string | null;
  currentModel: string;
  sidebarCollapsed: boolean;
  conversationTitles: Record<string, string>;
  setCurrentConversation: (id: string | null) => void;
  setCurrentModel: (model: string) => void;
  toggleSidebar: () => void;
  updateConversationTitle: (id: string, title: string) => void;
}

export const useConversationStore = create<ConversationState>()(
  persist(
    (set) => ({
      currentConversationId: null,
      currentModel: "",
      sidebarCollapsed: false,
      conversationTitles: {},
      setCurrentConversation: (id) => set({ currentConversationId: id }),
      setCurrentModel: (model) => set({ currentModel: model }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      updateConversationTitle: (id, title) =>
        set((state) => ({
          conversationTitles: { ...state.conversationTitles, [id]: title },
        })),
    }),
    {
      name: "harmony-conversation-ui",
      partialize: (state) => ({ sidebarCollapsed: state.sidebarCollapsed }),
    },
  ),
);
