"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const onModels = path === "/" || path.startsWith("/models");

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/login";
  }

  return (
    <div className="rahmen">
      <aside className="leiste">
        <div className="marke">OG <span>Scale</span></div>
        <nav aria-label="Bereiche">
          <Link href="/" aria-current={onModels ? "page" : undefined}>Models &amp; Nischen</Link>
          <span className="bald">Content <em>in Arbeit</em></span>
          <span className="bald">AliRemote <em>in Arbeit</em></span>
        </nav>
        <div className="unten">
          <button onClick={logout}>Abmelden</button>
        </div>
      </aside>
      <main className="inhalt">{children}</main>
    </div>
  );
}
