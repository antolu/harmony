import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { api } from "@/shared/api/client";
import type { ModelRegistryEntry } from "@/shared/api/client";
import { Combobox } from "@/shared/components/ui/combobox";

const NO_KEY_OPTION = "No key";
export const CLEAR_API_KEY = "__clear__";

export function ApiKeyCell({
  entry,
  onSelectExisting,
  onCreate,
  onClear,
  isPending,
}: {
  entry: ModelRegistryEntry;
  onSelectExisting: (id: string) => void;
  onCreate: (name: string, value: string) => void;
  onClear: () => void;
  isPending: boolean;
}) {
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyValue, setNewKeyValue] = useState("");

  const { data: llmApiKeys } = useQuery({
    queryKey: ["llmApiKeys"],
    queryFn: api.listLlmApiKeys,
    staleTime: 30_000,
  });

  if (entry.env_override) {
    return (
      <div className="flex items-center gap-1 text-yellow-600">
        <Lock className="h-3 w-3" />
        <span className="text-xs">ENV override</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <Combobox
        options={[NO_KEY_OPTION, ...(llmApiKeys ?? []).map((k) => k.name)]}
        value={newKeyName || entry.api_key_name || ""}
        onChange={(v) => {
          if (v === NO_KEY_OPTION) {
            onClear();
            setNewKeyName("");
            setNewKeyValue("");
            return;
          }
          const id = llmApiKeys?.find((k) => k.name === v)?.id;
          if (id) {
            onSelectExisting(id);
            setNewKeyName("");
            setNewKeyValue("");
          }
        }}
        onCreate={(name) => {
          setNewKeyName(name);
          setNewKeyValue("");
        }}
        createLabel={(v) => `Create new key "${v}"`}
        placeholder="Not set"
        searchPlaceholder="Search keys..."
        disabled={isPending}
        variant="inline"
      />
      {newKeyName && (
        <>
          <Input
            type="password"
            value={newKeyValue}
            onChange={(e) => setNewKeyValue(e.target.value)}
            className="h-7 w-32 text-xs"
            placeholder={`Secret for "${newKeyName}"`}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && newKeyValue && !isPending) {
                onCreate(newKeyName, newKeyValue);
                setNewKeyName("");
                setNewKeyValue("");
              }
            }}
          />
          <Button
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              onCreate(newKeyName, newKeyValue);
              setNewKeyName("");
              setNewKeyValue("");
            }}
            disabled={!newKeyValue || isPending}
          >
            Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setNewKeyName("");
              setNewKeyValue("");
            }}
          >
            Cancel
          </Button>
        </>
      )}
    </div>
  );
}
