import Link from "next/link";
import React from "react";
import type { ReactNode } from "react";

type ShellProps = {
  children: ReactNode;
};

export function Shell({ children }: ShellProps) {
  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">SS</span>
          <span>ScaleScrape Target Lab</span>
        </Link>
        <nav className="nav" aria-label="Cenarios">
          <Link href="/items?page=1">Produtos</Link>
          <Link href="/protected/items?page=1">Risco</Link>
          <Link href="/external/items?page=1">Fonte externa</Link>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/antibot/debug/session">Debug</Link>
        </nav>
      </header>
      {children}
    </div>
  );
}
