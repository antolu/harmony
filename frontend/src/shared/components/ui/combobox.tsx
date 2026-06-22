"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Plus } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/shared/components/ui/command";
import { Input } from "@/shared/components/ui/input";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/shared/components/ui/popover";

interface ComboboxProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  /** When provided, typing a value with no exact match shows a "Create…" option. */
  onCreate?: (value: string) => void;
  createLabel?: (value: string) => string;
  /**
   * "default": standard bordered input look, always.
   * "inline": reads as plain text (no border/background) until opened —
   * for use as an inline editable field embedded in other content (e.g. a table cell).
   */
  variant?: "default" | "inline";
  /** When true, clicking the already-selected option clears it. Default false (re-selecting is a no-op). */
  allowDeselect?: boolean;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Select...",
  searchPlaceholder = "Search...",
  emptyText = "No results found.",
  disabled = false,
  onCreate,
  createLabel = (v) => `Create "${v}"`,
  variant = "default",
  allowDeselect = false,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const filteredOptions = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return options;
    }

    return options.filter((option) =>
      option.toLowerCase().includes(normalizedQuery),
    );
  }, [options, query]);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);

    if (!nextOpen) {
      setQuery("");
    }
  };

  const inputValue = open ? query : value;
  const trimmedQuery = query.trim();
  const hasExactMatch = filteredOptions.some(
    (option) => option.toLowerCase() === trimmedQuery.toLowerCase(),
  );
  const canCreate = !!onCreate && trimmedQuery.length > 0 && !hasExactMatch;
  const isInline = variant === "inline";
  const inlineAtRest = isInline && !open;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverAnchor asChild>
        <div className="relative">
          <Input
            role="combobox"
            aria-expanded={open}
            value={inputValue}
            placeholder={open ? searchPlaceholder : placeholder}
            disabled={disabled}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onClick={() => setOpen(true)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.currentTarget.blur();
                handleOpenChange(false);
              } else if (event.key === "ArrowDown" && !open) {
                event.preventDefault();
                setOpen(true);
              }
            }}
            className={cn(
              isInline ? "pr-2" : "pr-9",
              !value && !open && "text-muted-foreground",
              isInline && "h-7 px-2 text-xs focus-visible:ring-1",
              inlineAtRest &&
                "cursor-pointer border-transparent bg-transparent shadow-none hover:border-input focus-visible:cursor-text",
            )}
          />
          {!isInline && (
            <button
              type="button"
              aria-label="Toggle options"
              disabled={disabled}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => handleOpenChange(!open)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-muted-foreground opacity-70 hover:opacity-100 disabled:pointer-events-none disabled:opacity-50"
            >
              <ChevronsUpDown className="h-4 w-4" />
            </button>
          )}
        </div>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        className="w-[--radix-popover-trigger-width] p-0"
        disablePortal
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <Command>
          <CommandList>
            {filteredOptions.length === 0 && !canCreate ? (
              <div className="py-6 text-center text-sm">{emptyText}</div>
            ) : (
              <CommandGroup>
                {filteredOptions.map((opt) => (
                  <CommandItem
                    key={opt}
                    value={opt}
                    onSelect={() => {
                      onChange(opt === value && allowDeselect ? "" : opt);
                      handleOpenChange(false);
                    }}
                  >
                    {value === opt && (
                      <Check className="mr-2 h-4 w-4 shrink-0" />
                    )}
                    {opt}
                  </CommandItem>
                ))}
                {canCreate && (
                  <CommandItem
                    key="__create__"
                    value={`__create__${trimmedQuery}`}
                    onSelect={() => {
                      onCreate?.(trimmedQuery);
                      handleOpenChange(false);
                    }}
                  >
                    <Plus className="mr-2 h-4 w-4 shrink-0" />
                    {createLabel(trimmedQuery)}
                  </CommandItem>
                )}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
