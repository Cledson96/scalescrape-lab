import {
  EXTERNAL_RECORD_TOTAL,
  LOCAL_RECORD_TOTAL,
  PROTECTED_RECORD_TOTAL,
  UNSTABLE_RECORD_TOTAL
} from "./site-contracts";

export type PublicRecord = {
  externalId: string;
  title: string;
  category: string;
  region: string;
  status: string;
  riskScore: number;
  sourceLabel: string;
  rawSummary: string;
  fetchedAt?: string;
};

export type RecordPage = {
  records: PublicRecord[];
  pageNumber: number;
  perPage: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
};

type RandomUserPayload = {
  results?: Array<{
    gender?: string;
    nat?: string;
    dob?: { age?: number };
    location?: {
      city?: string;
      state?: string;
      country?: string;
      timezone?: { description?: string };
    };
    email?: string;
    phone?: string;
  }>;
};

const areas = [
  "monitoramento cadastral",
  "analise de risco",
  "validacao de identidade",
  "consulta operacional",
  "prevencao a fraude",
  "conformidade regulatoria"
];

const regions = [
  "Curitiba PR",
  "Sao Paulo SP",
  "Belo Horizonte MG",
  "Florianopolis SC",
  "Porto Alegre RS",
  "Recife PE",
  "Goiania GO",
  "Fortaleza CE"
];

const statuses = ["ativo", "em analise", "atualizado", "monitorado"];

const localCache = new Map<string, PublicRecord[]>();
let externalCache: PublicRecord[] | null = null;
let externalCacheFetchedAt: Date | null = null;

export const EXTERNAL_CACHE_TTL_MS = 6 * 60 * 60 * 1000;

export function isExternalCacheFresh(fetchedAt: Date | null, now = new Date()): boolean {
  if (!fetchedAt) {
    return false;
  }
  return now.getTime() - fetchedAt.getTime() < EXTERNAL_CACHE_TTL_MS;
}

export function getLocalRecords({ prefix = "normal", total = 240 }: { prefix?: string; total?: number } = {}): PublicRecord[] {
  const safeTotal = Math.max(1, total);
  const cacheKey = `${prefix}:${safeTotal}`;
  const cached = localCache.get(cacheKey);
  if (cached) {
    return [...cached];
  }

  const records = Array.from({ length: safeTotal }, (_, offset) => {
    const index = offset + 1;
    const area = areas[offset % areas.length];
    const region = regions[(index * 3) % regions.length];
    const status = statuses[(index * 5) % statuses.length];
    const riskScore = 12 + ((index * 17) % 79);

    return {
      externalId: `${prefix}-${index}`,
      title: `Registro publico ${String(index).padStart(3, "0")} - ${area}`,
      category: area,
      region,
      status,
      riskScore,
      sourceLabel: "dataset local sintetico",
      rawSummary: `fonte=local; lote=${1 + Math.floor(offset / 25)}; prioridade=${1 + (index % 5)}; checksum=${prefix}-${index * 37}`
    };
  });

  localCache.set(cacheKey, records);
  return [...records];
}

export function paginateRecords(records: PublicRecord[], pageNumber: number, perPage = 12): RecordPage {
  const safePerPage = Math.max(1, perPage);
  const total = records.length;
  const totalPages = Math.max(1, Math.ceil(total / safePerPage));
  const safePage = Math.min(Math.max(1, pageNumber), totalPages);
  const start = (safePage - 1) * safePerPage;

  return {
    records: records.slice(start, start + safePerPage),
    pageNumber: safePage,
    perPage: safePerPage,
    total,
    totalPages,
    hasNext: safePage < totalPages,
    hasPrevious: safePage > 1
  };
}

export function normalizeRandomUserPayload(
  payload: RandomUserPayload,
  prefix = "external",
  fetchedAt = new Date().toISOString()
): PublicRecord[] {
  return (payload.results ?? []).map((item, offset) => {
    const index = offset + 1;
    const location = item.location ?? {};
    const country = location.country ?? "pais sintetico";
    const city = location.city ?? "cidade sintetica";
    const state = location.state ?? "estado sintetico";
    const timezone = location.timezone?.description ?? "n/a";
    const nat = item.nat ?? "ZZ";
    const age = item.dob?.age ?? "n/a";
    const gender = item.gender ?? "n/a";

    return {
      externalId: `${prefix}-${index}`,
      title: `Registro sintetico ${String(index).padStart(3, "0")} - ${country}`,
      category: `perfil sintetico ${nat}`,
      region: `${city}, ${state}, ${country}`,
      status: "importado",
      riskScore: 20 + ((index * 11) % 70),
      sourceLabel: "RandomUser fake API",
      rawSummary: `fonte=randomuser; importado_em=${fetchedAt}; idade_aproximada=${age}; genero=${gender}; fuso=${timezone}`,
      fetchedAt
    };
  });
}

export async function getExternalRecords(size = 500): Promise<PublicRecord[]> {
  if (externalCache && isExternalCacheFresh(externalCacheFetchedAt)) {
    return [...externalCache];
  }

  const safeSize = Math.max(1, Math.min(size, 5000));
  const params = new URLSearchParams({
    results: String(safeSize),
    seed: "scalescrape-lab",
    nat: "br,us,gb,es,fr",
    noinfo: ""
  });

  try {
    const fetchedAt = new Date();
    const response = await fetch(`https://randomuser.me/api/?${params.toString()}`, {
      next: { revalidate: EXTERNAL_CACHE_TTL_MS / 1000 }
    });
    if (!response.ok) {
      throw new Error(`RandomUser returned ${response.status}`);
    }
    externalCacheFetchedAt = fetchedAt;
    externalCache = normalizeRandomUserPayload((await response.json()) as RandomUserPayload, "external", fetchedAt.toISOString());
  } catch {
    externalCacheFetchedAt = new Date();
    externalCache = getLocalRecords({ prefix: "external-fallback", total: safeSize });
  }

  return [...externalCache];
}

export async function findRecord(recordId: string): Promise<PublicRecord | undefined> {
  const pools = [
    getLocalRecords({ prefix: "normal", total: LOCAL_RECORD_TOTAL }),
    getLocalRecords({ prefix: "protected", total: PROTECTED_RECORD_TOTAL }),
    getLocalRecords({ prefix: "unstable", total: UNSTABLE_RECORD_TOTAL }),
    await getExternalRecords(EXTERNAL_RECORD_TOTAL)
  ];

  return pools.flat().find((record) => record.externalId === recordId);
}
