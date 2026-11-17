"use client";

// Ported from Lumeo theme-toggle.tsx (sharp hairline box, instant swap with transitions suppressed).
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { THEME_STORAGE_KEY } from "./theme-script";

type Theme = "dark" | "light";

function readTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    setTheme(readTheme());
  }, []);

  const toggle = () => {
    const next: Theme = readTheme() === "light" ? "dark" : "light";
    const root = document.documentElement;
    root.classList.add("theme-switching");
    root.setAttribute("data-theme", next);
    void root.offsetHeight;
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => root.classList.remove("theme-switching")));
    setTheme(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // storage unavailable: the toggle still works for this page view
    }
  };

  const isLight = theme === "light";
  const label = theme === null ? "Toggle colour theme" : `Switch to ${isLight ? "dark" : "light"} theme`;

  return (
    <button type="button" onClick={toggle} className={`theme-toggle ${className}`} aria-label={label} title={label}>
      <span className="theme-toggle-icon" aria-hidden="true">
        {theme === null ? null : isLight ? <Moon className="h-[15px] w-[15px]" /> : <Sun className="h-[15px] w-[15px]" />}
      </span>
    </button>
  );
}
