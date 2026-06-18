import { useEffect, useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";

type Theme = "light" | "dark" | "system";

const THEME_KEY = "harmony.theme";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "light") {
    root.classList.remove("dark");
  } else if (theme === "dark") {
    root.classList.add("dark");
  } else {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (mq.matches) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }
}

export function ThemeToggle({ isLoggedIn = false }: { isLoggedIn?: boolean }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
    return "system";
  });

  useEffect(() => {
    applyTheme(theme);

    if (theme !== "system") return;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      document.documentElement.classList.toggle("dark", e.matches);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  function handleChange(next: Theme) {
    setTheme(next);
    localStorage.setItem(THEME_KEY, next);
    if (isLoggedIn) {
      api.updatePreferences({ theme: next });
    }
  }

  const options: { value: Theme; icon: React.ReactNode; label: string }[] = [
    { value: "light", icon: <Sun className="h-4 w-4" />, label: "Light" },
    { value: "dark", icon: <Moon className="h-4 w-4" />, label: "Dark" },
    { value: "system", icon: <Monitor className="h-4 w-4" />, label: "System" },
  ];

  return (
    <div className="flex items-center gap-1">
      {options.map((opt) => (
        <Button
          key={opt.value}
          variant={theme === opt.value ? "secondary" : "ghost"}
          size="icon"
          className="h-8 w-8"
          aria-label={opt.label}
          onClick={() => handleChange(opt.value)}
        >
          {opt.icon}
        </Button>
      ))}
    </div>
  );
}
