export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export type Indicator = {
  code: string;
  label: string;
  definition: string;
  unit: string;
  periodicity: string;
  methodology: string;
  limitations: string;
  domain: string;
};

export type SourceInfo = {
  provider: string;
  dataset: string;
  url: string;
  sha256: string;
  fetched_at: string;
  license: string | null;
  source_status: string;
  connector_status: string;
};

export type Observation = {
  period_start: string;
  period_end: string;
  scope: Record<string, unknown>;
  value: string | number | null;
  availability_status: string;
  revision: number;
  source_reference_at: string | null;
  retrieved_at: string;
  source: SourceInfo;
};

export type IndicatorResponse = {
  indicator: Indicator;
  municipality_ibge_code: string;
  municipality: { ibge_code: string; name: string; state: string };
  items: Observation[];
  count: number;
};

export type Municipality = { ibge_code: string; name: string; state: string };

export type SummaryCard = Observation & { indicator: Indicator };

export type MunicipalitySummary = {
  municipality: Municipality;
  generated_at: string;
  cards: SummaryCard[];
  available_indicators: SummaryCard[];
  datasets: Array<{
    code: string;
    title: string;
    domain: string;
    status: string;
    publication_status: string;
  }>;
  sectors: Array<{ slug: string; candidate_sources: number; published_datasets: number }>;
  catalog_summary: { candidate_sources: number; published_datasets: number };
};

export type SearchItem = {
  id: string;
  title: string;
  description: string | null;
  area: string;
  area_label: string;
  provider: { slug: string; name: string };
  resource: null | {
    slug: string;
    title: string;
    url: string | null;
    format: string;
    source_status: string;
    connector_status: string;
    license_status: string;
    license: string | null;
    last_verified_at: string | null;
  };
  dataset: null | {
    id: string;
    code: string;
    granularity: string;
    update_policy: string;
    publication_status: string;
  };
  status: string;
  source_status: string;
  connector_status: string;
  publication_status: string;
  reference_period: string | null;
  collected_at: string | null;
};

export type Facet = { value: string; count: number };

export type SearchResponse = {
  items: SearchItem[];
  municipalities: Municipality[];
  count: number;
  limit: number;
  offset: number;
  facets: {
    sectors: Facet[];
    providers: Facet[];
    formats: Facet[];
    resources: Facet[];
    license_statuses: Facet[];
    statuses: Facet[];
    freshness: Facet[];
  };
  summary: { candidate_sources: number; published_datasets: number };
};

export async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}/v1${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Falha na API (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function formatValue(value: string | number | null, unit: string): string {
  if (value === null || value === undefined) return "Não disponível";
  const numeric = Number(value);
  if (unit === "BRL nominal") {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 0,
    }).format(numeric);
  }
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(numeric);
}

export function formatDate(value: string | null): string {
  if (!value) return "não informada pela fonte";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "medium",
  }).format(new Date(value));
}

