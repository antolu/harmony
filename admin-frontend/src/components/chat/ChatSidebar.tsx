import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, Shield } from "lucide-react";
import { api } from "@/api/client";
import { useConversationStore } from "@/stores/chatStore";
import { ConversationItem } from "@/components/chat/ConversationItem";
import { ConversationBrowser } from "@/components/chat/ConversationBrowser";
import { UserMenu } from "@/components/chat/UserMenu";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

function dateBucket(
  updatedAt: string,
): "today" | "yesterday" | "last7" | "older" {
  const now = new Date();
  const date = new Date(updatedAt);
  const dayMs = 24 * 60 * 60 * 1000;
  const diffDays = Math.floor((now.getTime() - date.getTime()) / dayMs);
  const sameDay =
    now.getFullYear() === date.getFullYear() &&
    now.getMonth() === date.getMonth() &&
    now.getDate() === date.getDate();
  if (sameDay) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return "last7";
  return "older";
}

const BUCKET_LABELS: Record<string, string> = {
  today: "Today",
  yesterday: "Yesterday",
  last7: "Last 7 days",
  older: "Older",
};
const BUCKET_ORDER = ["today", "yesterday", "last7", "older"] as const;

interface ChatSidebarProps {
  onClose?: () => void;
}

export function ChatSidebar({ onClose }: ChatSidebarProps) {
  const navigate = useNavigate();
  const { conversationId } = useParams<{ conversationId: string }>();
  const { sidebarCollapsed, toggleSidebar, setCurrentConversation } =
    useConversationStore();
  const [browserOpen, setBrowserOpen] = useState(false);

  const { data: convsData } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.getConversations(20, 0),
    staleTime: 30_000,
  });

  const { data: userDataRaw } = useQuery({
    queryKey: ["current-user"],
    queryFn: () => api.getCurrentUser(),
    retry: false,
    staleTime: 60_000,
  });

  const currentUser = userDataRaw ?? null;
  const conversations = convsData?.conversations ?? [];

  const grouped = BUCKET_ORDER.reduce(
    (acc, bucket) => {
      acc[bucket] = conversations.filter(
        (c) => dateBucket(c.updated_at) === bucket,
      );
      return acc;
    },
    {} as Record<string, typeof conversations>,
  );

  function NavItem({
    icon,
    label,
    onClick,
  }: {
    icon: React.ReactNode;
    label: string;
    onClick: () => void;
  }) {
    if (sidebarCollapsed) {
      return (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              aria-label={label}
              onClick={onClick}
            >
              {icon}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
      );
    }
    return (
      <Button
        variant="ghost"
        className="w-full justify-start gap-2"
        onClick={onClick}
      >
        {icon}
        {label}
      </Button>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <aside
        role="navigation"
        aria-label="Chat navigation"
        className={cn(
          "flex h-screen flex-col border-r bg-muted/40 transition-all duration-200 ease-in-out",
          sidebarCollapsed ? "w-12" : "w-64",
        )}
      >
        {/* Collapse toggle */}
        <div
          className={cn(
            "flex items-center p-2",
            sidebarCollapsed ? "justify-center" : "justify-end",
          )}
        >
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 min-h-[44px] min-w-[44px]"
                aria-label={
                  sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
                }
                onClick={toggleSidebar}
              >
                {sidebarCollapsed ? (
                  <ChevronRight className="h-4 w-4" />
                ) : (
                  <ChevronLeft className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            </TooltipContent>
          </Tooltip>
        </div>

        {/* New chat button */}
        <div
          className={cn("px-2 pb-2", sidebarCollapsed && "flex justify-center")}
        >
          {sidebarCollapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 min-h-[44px] min-w-[44px]"
                  aria-label="New chat"
                  onClick={() => {
                    setCurrentConversation(null);
                    navigate("/");
                    onClose?.();
                  }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">New chat</TooltipContent>
            </Tooltip>
          ) : (
            <Button
              variant="ghost"
              className="w-full justify-start gap-2"
              onClick={() => {
                setCurrentConversation(null);
                navigate("/");
                onClose?.();
              }}
            >
              <Plus className="h-4 w-4" />
              New chat
            </Button>
          )}
        </div>

        {/* Conversation list */}
        <ScrollArea className="flex-1 px-2">
          {sidebarCollapsed ? (
            <div className="flex flex-col items-center gap-0.5">
              {conversations.map((c) => (
                <Tooltip key={c.id}>
                  <TooltipTrigger asChild>
                    <button
                      aria-label={c.title || "Untitled conversation"}
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-md text-sm font-semibold",
                        conversationId === c.id
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted text-foreground",
                      )}
                      onClick={() => navigate(`/c/${c.id}`)}
                    >
                      {(c.title || "U").charAt(0).toUpperCase()}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    {c.title || "Untitled conversation"}
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          ) : (
            <div className="space-y-3 pb-2">
              {BUCKET_ORDER.filter((b) => grouped[b].length > 0).map(
                (bucket) => (
                  <div key={bucket}>
                    <p className="mb-1 px-2 text-xs text-muted-foreground">
                      {BUCKET_LABELS[bucket]}
                    </p>
                    {grouped[bucket].map((c) => (
                      <ConversationItem
                        key={c.id}
                        conversation={c}
                        isActive={conversationId === c.id}
                      />
                    ))}
                  </div>
                ),
              )}

              {conversations.length === 0 && (
                <p className="px-2 text-xs text-muted-foreground">
                  No conversations yet
                </p>
              )}
            </div>
          )}
        </ScrollArea>

        {/* Show all button */}
        {!sidebarCollapsed && conversations.length > 0 && (
          <div className="px-2 pb-1">
            <Button
              variant="ghost"
              className="w-full justify-start text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setBrowserOpen(true)}
            >
              Show all
            </Button>
          </div>
        )}
        {sidebarCollapsed && (
          <div className="flex justify-center px-2 pb-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground"
                  aria-label="Show all conversations"
                  onClick={() => setBrowserOpen(true)}
                >
                  <span className="text-xs font-bold">···</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Show all</TooltipContent>
            </Tooltip>
          </div>
        )}

        <Separator />

        {/* Admin nav item */}
        {currentUser?.harmony_role === "admin" && (
          <div
            className={cn(
              "px-2 py-1",
              sidebarCollapsed && "flex justify-center",
            )}
          >
            <NavItem
              icon={<Shield className="h-4 w-4" />}
              label="Admin"
              onClick={() => navigate("/admin")}
            />
          </div>
        )}

        {/* User menu */}
        <div className="p-2">
          {sidebarCollapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex justify-center">
                  <div
                    className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold"
                    aria-label="User menu"
                  >
                    {currentUser
                      ? (currentUser.display_name || currentUser.email || "U")
                          .charAt(0)
                          .toUpperCase()
                      : "U"}
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent side="right">
                {currentUser?.display_name || currentUser?.email || "User"}
              </TooltipContent>
            </Tooltip>
          ) : currentUser ? (
            <UserMenu user={currentUser} />
          ) : (
            <div className="h-9" />
          )}
        </div>

        <ConversationBrowser open={browserOpen} onOpenChange={setBrowserOpen} />
      </aside>
    </TooltipProvider>
  );
}
