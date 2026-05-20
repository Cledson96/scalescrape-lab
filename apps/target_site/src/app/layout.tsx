import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Shell } from "../components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScaleScrape Target Lab",
  description: "Laboratorio local de scraping, risco cadastral e simulacao anti-fraude."
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR">
      <head>
        <script src="https://www.google.com/recaptcha/api.js" async defer />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
