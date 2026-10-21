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

