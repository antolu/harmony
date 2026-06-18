import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Button } from "@/shared/components/ui/button";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { cn } from "@/shared/lib/utils";

interface ConversationBrowserProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const PAGE_SIZE = 20;

export function ConversationBrowser({
  open,
  onOpenChange,
}: ConversationBrowserProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const { data } = useQuery({
    queryKey: ["conversations-all"],
    queryFn: () => api.getConversations(100, 0),
    enabled: open,
  });

  const conversations = data?.conversations ?? [];
  const isTruncated = conversations.length >= 100;

  const filtered = conversations.filter((c) => {
    const term = search.toLowerCase();
    return !term || (c.title ?? "").toLowerCase().includes(term);
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageItems = filtered.slice(
    currentPage * PAGE_SIZE,
    (currentPage + 1) * PAGE_SIZE,
  );

  function handleSelect(id: string) {
    onOpenChange(false);
    navigate(`/c/${id}`);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            All conversations
          </DialogTitle>
        </DialogHeader>

        {isTruncated && (
          <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
            Showing the 100 most recent conversations. Older ones may not appear
            here.
          </p>
        )}

        <Input
          placeholder="Search conversations..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="mt-2"
        />

        <ScrollArea className="mt-3 h-80">
          {pageItems.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No conversations match your search.
            </p>
          ) : (
            <div className="space-y-0.5 pr-2">
              {pageItems.map((c) => (
                <button
                  key={c.id}
                  className={cn(
                    "w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
                  onClick={() => handleSelect(c.id)}
                >
                  <span className="block truncate font-semibold">
                    {c.title || "Untitled conversation"}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(c.updated_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              {currentPage + 1} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
