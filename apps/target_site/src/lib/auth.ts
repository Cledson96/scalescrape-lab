import { DEFAULT_PROTECTED_PATH, PUBLIC_EXACT_PATHS, PUBLIC_PATH_PREFIXES } from "./site-contracts";

export type AuthEnv = Record<string, string | undefined>;

const PUBLIC_EXACT_PATH_SET = new Set(PUBLIC_EXACT_PATHS);

export function validateLoginCredentials(username: string, password: string, env: AuthEnv = process.env): boolean {
  const expectedUsername = env.TARGET_SITE_USERNAME || "demo";
  const expectedPassword = env.TARGET_SITE_PASSWORD || "demo123";
  return username === expectedUsername && password === expectedPassword;
}

export function normalizeNextPath(candidate: string | null | undefined): string {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) {
    return DEFAULT_PROTECTED_PATH;
  }
  if (candidate.startsWith("/login")) {
    return DEFAULT_PROTECTED_PATH;
  }
  return candidate;
}

export function isPublicTargetPath(pathname: string): boolean {
  if (PUBLIC_EXACT_PATH_SET.has(pathname as (typeof PUBLIC_EXACT_PATHS)[number])) {
    return true;
  }
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
