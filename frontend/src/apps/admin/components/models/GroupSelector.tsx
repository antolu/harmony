import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Switch } from "@/shared/components/ui/switch";
import { api } from "@/shared/api/client";

export function GroupSelector({
  entryId,
  allowedGroups,
  onUpdate,
}: {
  entryId: string;
  allowedGroups: string[];
  onUpdate: (id: string, groups: string[]) => void;
}) {
  const { data: groups } = useQuery({
    queryKey: ["adminGroups"],
    queryFn: api.getGroups,
    staleTime: 60_000,
  });

  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>(allowedGroups);

  const toggle = (role: string) => {
    setSelected((prev) =>
      prev.includes(role) ? prev.filter((g) => g !== role) : [...prev, role],
    );
  };

  const handleSave = () => {
    onUpdate(entryId, selected);
    setOpen(false);
  };

  if (!groups || groups.length === 0) {
    return <span className="text-xs text-muted-foreground">No groups</span>;
  }

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {allowedGroups.length === 0 ? (
        <span className="text-xs text-muted-foreground">All groups</span>
      ) : (
        allowedGroups.slice(0, 2).map((g) => (
          <Badge key={g} variant="secondary" className="text-xs">
            {g}
          </Badge>
        ))
      )}
      {allowedGroups.length > 2 && (
        <span className="text-xs text-muted-foreground">
          +{allowedGroups.length - 2}
        </span>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-1 text-xs"
          onClick={() => {
            setSelected(allowedGroups);
            setOpen(true);
          }}
        >
          Edit
        </Button>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Assign Groups</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {groups.map((role) => (
              <div
                key={role}
                className="flex items-center justify-between rounded border px-3 py-2"
              >
                <span className="text-sm">{role}</span>
                <Switch
                  checked={selected.includes(role)}
                  onCheckedChange={() => toggle(role)}
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
