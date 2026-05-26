import { create } from "zustand";

export interface Conversation {
  id: string;
  title: string | null;
  mode: "search" | "chat";
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ title: string; url: string; snippet: string }>;
}

interface ConversationState {
  currentConversationId: string | null;
  conversations: Conversation[];
  messages: Message[];
  currentModel: string;
  currentMode: "search" | "deep_research" | "chat";
  sidebarCollapsed: boolean;
  setCurrentConversation: (id: string | null) => void;
  setConversations: (convs: Conversation[]) => void;
  addMessage: (msg: Message) => void;
  setMessages: (msgs: Message[]) => void;
  updateConversationTitle: (id: string, title: string) => void;
  setCurrentModel: (model: string) => void;
  setCurrentMode: (mode: ConversationState["currentMode"]) => void;
  toggleSidebar: () => void;
}

const SIDEBAR_KEY = "harmony.sidebar.collapsed";

export const useConversationStore = create<ConversationState>((set) => ({
  currentConversationId: null,
  conversations: [],
  messages: [],
  currentModel: "",
  currentMode: "search",
  sidebarCollapsed: localStorage.getItem(SIDEBAR_KEY) === "true" ? true : false,
  setCurrentConversation: (id) => set({ currentConversationId: id }),
  setConversations: (convs) => set({ conversations: convs }),
  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
  setMessages: (msgs) => set({ messages: msgs }),
  updateConversationTitle: (id, title) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c,
      ),
    })),
  setCurrentModel: (model) => set({ currentModel: model }),
  setCurrentMode: (mode) => set({ currentMode: mode }),
  toggleSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      localStorage.setItem(SIDEBAR_KEY, String(next));
      return { sidebarCollapsed: next };
    }),
}));
