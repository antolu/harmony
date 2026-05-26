import { Outlet } from "react-router-dom";
import { ChatSidebar } from "@/components/chat/ChatSidebar";

export function ChatLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ChatSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
