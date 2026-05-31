import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useConversationStore } from "@/stores/chatStore";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface ConversationItemProps {
  conversation: {
    id: string;
    title: string | null;
    mode: string;
    updated_at: string;
    message_count: number;
  };
  isActive: boolean;
}

export function ConversationItem({
  conversation,
  isActive,
}: ConversationItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const updateConversationTitle = useConversationStore(
    (s) => s.updateConversationTitle,
  );
  const currentConversationId = useConversationStore(
    (s) => s.currentConversationId,
  );
  const setCurrentConversation = useConversationStore(
    (s) => s.setCurrentConversation,
  );

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(conversation.title ?? "");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const displayTitle = conversation.title || "Untitled conversation";

  const renameMutation = useMutation({
    mutationFn: (title: string) =>
      api.updateConversationTitle(conversation.id, title),
    onSuccess: (data) => {
      updateConversationTitle(conversation.id, data.title);
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteConversation(conversation.id),
    onSuccess: () => {
      setDeleteOpen(false);
      setDeleteError(null);
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (currentConversationId === conversation.id) {
        setCurrentConversation(null);
        navigate("/");
      }
    },
    onError: () => {
      setDeleteError("Failed to delete. Please try again.");
    },
  });

  function startEdit() {
    setEditValue(conversation.title ?? "");
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function commitEdit() {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== conversation.title) {
      renameMutation.mutate(trimmed);
    }
    setEditing(false);
  }

  function cancelEdit() {
    setEditing(false);
    setEditValue(conversation.title ?? "");
  }

  return (
    <>
      <div
        className={cn(
          "group relative flex w-full cursor-pointer items-center overflow-hidden rounded-md px-2 py-1.5 text-sm",
          isActive
            ? "bg-primary text-primary-foreground"
            : "hover:bg-muted text-foreground",
        )}
        onClick={() => {
          if (!editing) navigate(`/c/${conversation.id}`);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !editing) navigate(`/c/${conversation.id}`);
        }}
      >
        {editing ? (
          <Input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitEdit();
              if (e.key === "Escape") cancelEdit();
            }}
            className="h-6 py-0 text-sm"
            placeholder="Conversation title"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="flex-1 truncate font-semibold">{displayTitle}</span>
        )}

        {!editing && (
          <div
            className={cn(
              "absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity",
              isActive && "opacity-0 group-hover:opacity-100",
            )}
          >
            <button
              aria-label="Rename conversation"
              className="rounded p-0.5 hover:bg-muted-foreground/20"
              onClick={(e) => {
                e.stopPropagation();
                startEdit();
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              aria-label="Delete conversation"
              className="rounded p-0.5 hover:bg-muted-foreground/20"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteOpen(true);
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <Dialog
        open={deleteOpen}
        onOpenChange={(open) => {
          setDeleteOpen(open);
          if (!open) setDeleteError(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete conversation</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This conversation and all its messages will be permanently deleted.
            This cannot be undone.
          </p>
          {deleteError && (
            <p className="text-sm text-destructive">{deleteError}</p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Keep conversation
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => {
                setDeleteError(null);
                deleteMutation.mutate();
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
