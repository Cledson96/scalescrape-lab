export const DEFAULT_PROTECTED_PATH = "/protected/items?page=1";
export const PUBLIC_EXACT_PATHS = ["/favicon.ico", "/robots.txt", "/sitemap.xml"] as const;
export const PUBLIC_PATH_PREFIXES = ["/login", "/captcha", "/_next"] as const;

export const ANTI_BOT_VISIT_WINDOW_MS = 60_000;
export const ANTI_BOT_RATE_LIMIT_VISITS = 12;
export const ANTI_BOT_HIGH_VOLUME_VISITS = 7;
export const ANTI_BOT_DELAY_MS = 400;

export const LOCAL_RECORD_TOTAL = 240;
export const PROTECTED_RECORD_TOTAL = 240;
export const UNSTABLE_RECORD_TOTAL = 120;
export const EXTERNAL_RECORD_TOTAL = 500;
export const ITEM_PAGE_SIZE = 12;
