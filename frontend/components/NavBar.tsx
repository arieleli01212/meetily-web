"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ListIcon,
  MicIcon,
  MoonIcon,
  SettingsIcon,
  SunIcon,
} from "./Icons";

const LINKS = [
  { href: "/", label: "Meetings", Icon: ListIcon, exact: true },
  { href: "/record", label: "Record", Icon: MicIcon },
  { href: "/settings", label: "Settings", Icon: SettingsIcon },
];

type Theme = "light" | "dark";

function applyTheme(t: Theme) {
  document.documentElement.setAttribute("data-theme", t);
  try {
    localStorage.setItem("meetily-theme", t);
  } catch {
    /* storage may be unavailable */
  }
}

export default function NavBar() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme | null>(null);

  // Read the theme the inline boot script already applied, so the toggle
  // reflects reality without causing a flash.
  useEffect(() => {
    const current = (document.documentElement.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark")) as Theme;
    setTheme(current);
  }, []);

  function toggle() {
    const next: Theme = theme === "light" ? "dark" : "light";
    applyTheme(next);
    setTheme(next);
  }

  return (
    <nav className="appbar">
      <Link href="/" className="brand">
        <span className="logo">
          <MicIcon size={17} />
        </span>
        Meetily
      </Link>

      <div className="links">
        {LINKS.map(({ href, label, Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`nav-link${active ? " active" : ""}`}
            >
              <Icon size={16} />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>

      <div className="spacer" />

      <button
        className="icon-btn"
        onClick={toggle}
        aria-label="Toggle theme"
        title={theme === "light" ? "Switch to dark" : "Switch to light"}
        suppressHydrationWarning
      >
        {theme === "light" ? <MoonIcon size={18} /> : <SunIcon size={18} />}
      </button>
    </nav>
  );
}
