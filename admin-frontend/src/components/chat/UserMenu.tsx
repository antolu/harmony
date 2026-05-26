import { useState } from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { LogOut, Settings } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ThemeToggle } from "@/components/chat/ThemeToggle";
import { cn } from "@/lib/utils";

interface UserMenuProps {
  user: {
    display_name: string | null;
    email: string | null;
    harmony_role: string;
  };
}

function getInitials(displayName: string | null, email: string | null): string {
  const name = displayName || email || "?";
  return name.charAt(0).toUpperCase();
}

export function UserMenu({ user }: UserMenuProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const initials = getInitials(user.display_name, user.email);
  const label = user.display_name || user.email || "User";

  return (
    <DropdownMenuPrimitive.Root open={open} onOpenChange={setOpen}>
      <DropdownMenuPrimitive.Trigger asChild>
        <button
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm",
            "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
          aria-label="User menu"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold">
            {initials}
          </div>
          <span className="truncate text-sm font-medium">{label}</span>
        </button>
      </DropdownMenuPrimitive.Trigger>

      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          side="top"
          align="start"
          sideOffset={4}
          className={cn(
            "z-50 min-w-[200px] rounded-md border bg-popover p-1 shadow-md",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
            "data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2",
          )}
        >
          <DropdownMenuPrimitive.Item
            onSelect={() => navigate("/admin/auth")}
            className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
          >
            <Settings className="h-4 w-4" />
            Account settings
          </DropdownMenuPrimitive.Item>

          <div className="flex items-center gap-2 rounded-sm px-2 py-1.5">
            <span className="text-sm text-muted-foreground">Theme</span>
            <ThemeToggle isLoggedIn />
          </div>

          <DropdownMenuPrimitive.Separator className="my-1 h-px bg-border" />

          <DropdownMenuPrimitive.Item
            onSelect={() => {
              window.location.href = "/api/auth/logout";
            }}
            className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </DropdownMenuPrimitive.Item>
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  );
}
