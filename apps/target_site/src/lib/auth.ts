export type AuthEnv = Record<string, string | undefined>;

const defaultProtectedPath = "/protected/items?page=1";

export function validateLoginCredentials(username: string, password: string, env: AuthEnv = process.env): boolean {
  const expectedUsername = env.TARGET_SITE_USERNAME || "demo";
  const expectedPassword = env.TARGET_SITE_PASSWORD || "demo123";
  return username === expectedUsername && password === expectedPassword;
}

export function normalizeNextPath(candidate: string | null | undefined): string {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) {
    return defaultProtectedPath;
  }
  if (candidate.startsWith("/login")) {
    return defaultProtectedPath;
  }
  return candidate;
}
