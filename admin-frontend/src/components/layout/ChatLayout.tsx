import { Outlet } from "react-router-dom";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { useConversationStore } from "@/stores/chatStore";

export function ChatLayout() {
  const sidebarCollapsed = useConversationStore((s) => s.sidebarCollapsed);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ChatSidebar collapsed={sidebarCollapsed} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
