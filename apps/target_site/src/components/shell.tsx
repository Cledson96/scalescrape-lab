import Link from "next/link";
import type { ReactNode } from "react";

type ShellProps = {
  children: ReactNode;
};

export function Shell({ children }: ShellProps) {
  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">S</span>
          <span>
            <strong>ScaleScrape Target Lab</strong>
            <small>Data risk intelligence demo</small>
          </span>
        </Link>
        <nav className="nav" aria-label="Cenarios">
          <Link href="/items?page=1">Produtos</Link>
          <Link href="/protected/items?page=1">Risco</Link>
          <Link href="/external/items?page=1">Fonte externa</Link>
          <Link className="nav-primary" href="/dashboard">Dashboard</Link>
        </nav>
      </header>
      {children}
    </div>
  );
}
