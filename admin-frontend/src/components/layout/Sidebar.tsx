import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Globe,
  Database,
  ListTodo,
  Key,
  Settings,
  Cpu,
  Users,
  Link,
  ScrollText,
  Webhook,
  ArrowDownToLine,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const flatNavItems = [
  { to: "/admin", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/admin/crawler", icon: Globe, label: "Crawler Config" },
  { to: "/admin/jobs", icon: ListTodo, label: "Jobs" },
  { to: "/admin/auth", icon: Key, label: "Auth Sessions" },
  { to: "/admin/users", icon: Users, label: "Users" },
  { to: "/admin/urls", icon: Link, label: "URLs" },
  { to: "/admin/audit-log", icon: ScrollText, label: "Audit Log" },
  { to: "/admin/webhooks", icon: Webhook, label: "Webhooks" },
];

const settingsChildren = [
  { to: "/admin/settings", icon: Settings, label: "General" },
  { to: "/admin/models", icon: Cpu, label: "Models" },
  { to: "/admin/indexer", icon: Database, label: "Indexer Config" },
];

const exportItem = {
  to: "/admin/export",
  icon: ArrowDownToLine,
  label: "Export / Import",
};

export function Sidebar() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const location = useLocation();
  const isSettingsActive = settingsChildren.some((c) =>
    location.pathname.startsWith(c.to),
  );

  return (
    <aside className="w-64 border-r bg-muted/40 p-4">
      <div className="mb-8">
        <h1 className="text-xl font-bold">Harmony Admin</h1>
        <p className="text-sm text-muted-foreground">Crawling System</p>
      </div>

      <nav className="space-y-1">
        {flatNavItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}

        <button
          onClick={() => setSettingsOpen((o) => !o)}
          className={cn(
            "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground",
            isSettingsActive ? "text-foreground" : "text-muted-foreground",
          )}
        >
          <Settings className="h-4 w-4" />
          <span className="flex-1 text-left">Settings</span>
          {settingsOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        {settingsOpen && (
          <div className="ml-4 space-y-1">
            {settingsChildren.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            ))}
          </div>
        )}

        <NavLink
          to={exportItem.to}
          end
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )
          }
        >
          <exportItem.icon className="h-4 w-4" />
          {exportItem.label}
        </NavLink>
      </nav>
    </aside>
  );
}
