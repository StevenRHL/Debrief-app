"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { loadSession, clearSession } from "../lib/auth";

export default function Nav() {
  const pathname = usePathname();
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    setUsername(loadSession()?.username ?? null);
  }, [pathname]);

  function signOut() {
    clearSession();
    setUsername(null);
  }

  const link = (href: string, label: string) => (
    <Link href={href} className={`nav-link${pathname === href ? " active" : ""}`}>{label}</Link>
  );

  return (
    <nav className="nav">
      <Link href="/" className="nav-brand">Debrief<span className="dot">.</span></Link>
      <div className="nav-links">
        {link("/play", "Play")}
        {link("/progress", "Progress")}
        {username ? (
          <>
            <span className="nav-user">{username}</span>
            <button className="link" onClick={signOut}>Sign out</button>
          </>
        ) : (
          link("/login", "Sign in")
        )}
      </div>
    </nav>
  );
}
