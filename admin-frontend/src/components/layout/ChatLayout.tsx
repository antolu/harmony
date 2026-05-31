import { useState, useEffect } from "react";
import { Outlet, useOutletContext } from "react-router-dom";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { cn } from "@/lib/utils";

type ChatLayoutContext = { onMobileMenuOpen: () => void };

export function useChatLayoutContext() {
  return useOutletContext<ChatLayoutContext>();
}

export function ChatLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (mobileMenuOpen) {
      document.documentElement.classList.add("overflow-hidden");
    } else {
      document.documentElement.classList.remove("overflow-hidden");
    }
    return () => {
      document.documentElement.classList.remove("overflow-hidden");
    };
  }, [mobileMenuOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <ChatSidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}
      <div
        className={cn(
          "fixed left-0 top-0 bottom-0 z-50 md:hidden transition-transform duration-300 ease-in-out",
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <ChatSidebar onClose={() => setMobileMenuOpen(false)} />
      </div>

      <div className="flex-1 overflow-hidden min-h-0 flex flex-col">
        <Outlet
          context={
            {
              onMobileMenuOpen: () => setMobileMenuOpen(true),
            } satisfies ChatLayoutContext
          }
        />
      </div>
    </div>
  );
}
