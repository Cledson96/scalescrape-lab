export function getPageNumber(searchParams?: { page?: string | string[] }): number {
  const rawPage = Array.isArray(searchParams?.page) ? searchParams?.page[0] : searchParams?.page;
  const parsed = Number.parseInt(rawPage ?? "1", 10);
  return Number.isFinite(parsed) ? Math.max(1, parsed) : 1;
}
