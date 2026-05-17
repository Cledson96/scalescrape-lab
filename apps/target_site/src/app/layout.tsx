import type { Metadata } from "next";
import React from "react";

import { Shell } from "../components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScaleScrape Target Lab",
  description: "Laboratorio local de scraping, risco cadastral e simulacao anti-fraude."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
