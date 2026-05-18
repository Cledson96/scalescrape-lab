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
  raw_data: Record<string, unknown>;
  created_at: string;
  extracted_at: string;
};

export type DashboardData = {
  jobs: JobSummary[];
  items: ExtractedItem[];
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
  }
} as const;

export type DashboardJobSource = keyof typeof dashboardJobPayloads | "all";

export function getApiBaseUrl(): string {
  return (process.env.SCALESCRAPE_API_URL || "http://api:8000").replace(/\/$/, "");
}

export async function fetchDashboardData(): Promise<DashboardData> {
  const apiBaseUrl = getApiBaseUrl();
  try {
    const [jobsResponse, itemsResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/jobs`, { cache: "no-store" }),
      fetch(`${apiBaseUrl}/items?limit=80`, { cache: "no-store" })
    ]);

    if (!jobsResponse.ok || !itemsResponse.ok) {
      throw new Error(`API retornou ${jobsResponse.status}/${itemsResponse.status}`);
    }

    return {
      jobs: (await jobsResponse.json()) as JobSummary[],
      items: (await itemsResponse.json()) as ExtractedItem[]
    };
  } catch (error) {
    return {
      jobs: [],
      items: [],
      apiError: error instanceof Error ? error.message : "Falha ao consultar a API"
    };
  }
}

export function payloadsForSource(source: DashboardJobSource): Array<(typeof dashboardJobPayloads)[keyof typeof dashboardJobPayloads]> {
  if (source === "all") {
    return [dashboardJobPayloads["fake-target"], dashboardJobPayloads["books-to-scrape"]];
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
