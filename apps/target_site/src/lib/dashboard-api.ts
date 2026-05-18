export type JobSummary = {
  id: number;
  source_id: number;
  start_url: string;
  public_url?: string;
  status: string;
  mode: string;
  max_pages: number;
  items_found: number;
  error_message: string | null;
  created_at: string;
};

export type ExtractedItem = {
  id: number;
  job_id: number;
  external_id: string;
  title: string;
  detail_url: string;
  public_detail_url?: string;
  public_image_url?: string | null;
  raw_data: Record<string, unknown>;
  created_at: string;
  extracted_at: string;
};

export type PaginatedItems = {
  items: ExtractedItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type DashboardData = {
  jobs: JobSummary[];
  items: ExtractedItem[];
  fakeItems: PaginatedItems;
  booksItems: PaginatedItems;
  globoItems: PaginatedItems;
  apiError?: string;
};

export const dashboardJobPayloads = {
  "fake-target": {
    source: "fake-target",
    start_url: "http://target-site:4000/protected/items?page=1",
    mode: "browser",
    max_pages: 1
  },
  "books-to-scrape": {
    source: "books-to-scrape",
    start_url: "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
    mode: "browser",
    max_pages: 1
  },
  "globo-home": {
    source: "globo-home",
    start_url: "https://www.globo.com/",
    mode: "browser",
    max_pages: 1
  }
} as const;

export type DashboardJobSource = keyof typeof dashboardJobPayloads | "all";

export function getApiBaseUrl(): string {
  return (process.env.SCALESCRAPE_API_URL || "http://api:8000").replace(/\/$/, "");
}

const emptyPage = (page = 1): PaginatedItems => ({
  items: [],
  total: 0,
  page,
  page_size: 10,
  total_pages: 0
});

function sourcePageUrl(apiBaseUrl: string, source: keyof typeof dashboardJobPayloads, page: number): string {
  const params = new URLSearchParams({
    source,
    page: String(page),
    page_size: "10"
  });
  return `${apiBaseUrl}/items/page?${params.toString()}`;
}

export async function fetchDashboardData(pages: { fakePage?: number; booksPage?: number; globoPage?: number } = {}): Promise<DashboardData> {
  const apiBaseUrl = getApiBaseUrl();
  const fakePage = pages.fakePage ?? 1;
  const booksPage = pages.booksPage ?? 1;
  const globoPage = pages.globoPage ?? 1;
  try {
    const [jobsResponse, itemsResponse, fakeResponse, booksResponse, globoResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/jobs`, { cache: "no-store" }),
      fetch(`${apiBaseUrl}/items?limit=80`, { cache: "no-store" }),
      fetch(sourcePageUrl(apiBaseUrl, "fake-target", fakePage), { cache: "no-store" }),
      fetch(sourcePageUrl(apiBaseUrl, "books-to-scrape", booksPage), { cache: "no-store" }),
      fetch(sourcePageUrl(apiBaseUrl, "globo-home", globoPage), { cache: "no-store" })
    ]);

    if (!jobsResponse.ok || !itemsResponse.ok || !fakeResponse.ok || !booksResponse.ok || !globoResponse.ok) {
      throw new Error(`API retornou ${jobsResponse.status}/${itemsResponse.status}/${fakeResponse.status}/${booksResponse.status}/${globoResponse.status}`);
    }

    return {
      jobs: (await jobsResponse.json()) as JobSummary[],
      items: (await itemsResponse.json()) as ExtractedItem[],
      fakeItems: (await fakeResponse.json()) as PaginatedItems,
      booksItems: (await booksResponse.json()) as PaginatedItems,
      globoItems: (await globoResponse.json()) as PaginatedItems
    };
  } catch (error) {
    return {
      jobs: [],
      items: [],
      fakeItems: emptyPage(fakePage),
      booksItems: emptyPage(booksPage),
      globoItems: emptyPage(globoPage),
      apiError: error instanceof Error ? error.message : "Falha ao consultar a API"
    };
  }
}

export function payloadsForSource(source: DashboardJobSource): Array<(typeof dashboardJobPayloads)[keyof typeof dashboardJobPayloads]> {
  if (source === "all") {
    return [dashboardJobPayloads["fake-target"], dashboardJobPayloads["books-to-scrape"], dashboardJobPayloads["globo-home"]];
  }
  return [dashboardJobPayloads[source]];
}

export async function createDashboardJobs(source: DashboardJobSource): Promise<number[]> {
  const apiBaseUrl = getApiBaseUrl();
  const responses = await Promise.all(
    payloadsForSource(source).map(async (payload) => {
      const response = await fetch(`${apiBaseUrl}/jobs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error(`Falha ao criar job ${payload.source}: ${response.status}`);
      }
      const data = (await response.json()) as { id: number };
      return data.id;
    })
  );
  return responses;
}
