import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
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
  PackageOpen,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";

const flatNavItems = [
  { to: "/admin", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/admin/jobs", icon: ListTodo, label: "Jobs" },
  { to: "/admin/auth", icon: Key, label: "Auth Sessions" },
  { to: "/admin/users", icon: Users, label: "Users" },
  { to: "/admin/audit-log", icon: ScrollText, label: "Audit Log" },
];

const dashboardItem = flatNavItems[0];
const restNavItems = flatNavItems.slice(1);

const dataSourcesChildren = [
  { to: "/admin/data-sources/new", icon: Plus, label: "New" },
];

const indexChildren = [
  { to: "/admin/urls", icon: Link, label: "URLs" },
  { to: "/admin/export", icon: ArrowDownToLine, label: "Export / Import" },
];

const settingsChildren = [
  { to: "/admin/settings", icon: Settings, label: "General" },
  { to: "/admin/models", icon: Cpu, label: "Models" },
  { to: "/admin/indexer", icon: Database, label: "Indexer Config" },
  { to: "/admin/webhooks", icon: Webhook, label: "Webhooks" },
];

function NavGroup({
  icon: Icon,
  label,
  to,
  children,
  childPaths,
}: {
  icon: React.ElementType;
  label: string;
  to?: string;
  children: { to: string; icon: React.ElementType; label: string }[];
  childPaths: string[];
}) {
  const location = useLocation();
  const isActive = to
    ? location.pathname === to ||
      childPaths.some((p) => location.pathname.startsWith(p))
    : childPaths.some((p) => location.pathname.startsWith(p));
  const [open, setOpen] = useState(isActive);

  useEffect(() => {
    if (isActive) setOpen(true);
  }, [isActive]);

  return (
    <>
      <div
        className={cn(
          "flex w-full items-center gap-3 rounded-md text-sm font-medium transition-colors hover:bg-muted hover:text-foreground",
          isActive ? "text-foreground" : "text-muted-foreground",
        )}
      >
        {to ? (
          <NavLink
            to={to}
            end
            className={({ isActive }) =>
              cn(
                "flex flex-1 items-center gap-3 px-3 py-2",
                isActive ? "text-foreground" : "",
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span className="flex-1 text-left">{label}</span>
          </NavLink>
        ) : (
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex flex-1 items-center gap-3 px-3 py-2 text-left"
          >
            <Icon className="h-4 w-4" />
            <span className="flex-1 text-left">{label}</span>
          </button>
        )}
        <button
          onClick={() => setOpen((o) => !o)}
          className="px-3 py-2"
          aria-label={open ? "Collapse" : "Expand"}
        >
          {open ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      </div>

      {open && (
        <div className="ml-4 space-y-1">
          {children.map((item) => (
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
    </>
  );
}

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-muted/40 p-4">
      <div className="mb-8">
        <h1 className="text-xl font-bold">Harmony Admin</h1>
        <p className="text-sm text-muted-foreground">Crawling System</p>
      </div>

      <nav className="space-y-1">
        <NavLink
          to={dashboardItem.to}
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
          <dashboardItem.icon className="h-4 w-4" />
          {dashboardItem.label}
        </NavLink>

        <NavGroup
          icon={Database}
          label="Data Sources"
          to="/admin/data-sources"
          children={dataSourcesChildren}
          childPaths={["/admin/data-sources"]}
        />

        {restNavItems.map((item) => (
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

        <NavGroup
          icon={PackageOpen}
          label="Index"
          children={indexChildren}
          childPaths={indexChildren.map((c) => c.to)}
        />

        <NavGroup
          icon={Settings}
          label="Settings"
          children={settingsChildren}
          childPaths={settingsChildren.map((c) => c.to)}
        />
      </nav>
    </aside>
  );
}
