export type PublicRecord = {
  externalId: string;
  title: string;
  category: string;
  region: string;
  status: string;
  riskScore: number;
  sourceLabel: string;
  rawSummary: string;
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

export function normalizeRandomUserPayload(payload: RandomUserPayload, prefix = "external"): PublicRecord[] {
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
      rawSummary: `fonte=randomuser; idade_aproximada=${age}; genero=${gender}; fuso=${timezone}`
    };
  });
}

export async function getExternalRecords(size = 500): Promise<PublicRecord[]> {
  if (externalCache) {
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
    const response = await fetch(`https://randomuser.me/api/?${params.toString()}`, {
      next: { revalidate: 3600 }
    });
    if (!response.ok) {
      throw new Error(`RandomUser returned ${response.status}`);
    }
    externalCache = normalizeRandomUserPayload((await response.json()) as RandomUserPayload);
  } catch {
    externalCache = getLocalRecords({ prefix: "external-fallback", total: safeSize });
  }

  return [...externalCache];
}

export async function findRecord(recordId: string): Promise<PublicRecord | undefined> {
  const pools = [
    getLocalRecords({ prefix: "normal", total: 240 }),
    getLocalRecords({ prefix: "protected", total: 240 }),
    getLocalRecords({ prefix: "unstable", total: 120 }),
    await getExternalRecords(500)
  ];

  return pools.flat().find((record) => record.externalId === recordId);
}
