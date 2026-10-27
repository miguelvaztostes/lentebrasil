"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  API_BASE,
  fetchJson,
  formatValue,
  type Municipality,
  type ResearchDictionary,
  type ResearchPoint,
  type ResearchSeries,
} from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";

const DEFAULT_GEOS = "3543402,3509502,3550308";
const COLORS = ["#119e9c", "#e3af42", "#315c7d", "#a64b7a", "#587d45", "#d56b3f", "#6750a4", "#287d8e"];
const domainNames: Record<string, string> = {
  "agropecuaria-e-rural": "Agropecuária e rural",
  desenvolvimento: "Desenvolvimento e população",
  "economia-e-trabalho": "Economia e trabalho",
  educacao: "Educação",
  "infraestrutura-e-cidades": "Infraestrutura e cidades",
  "protecao-social": "Proteção social",
  saude: "Saúde",
  transparencia: "Transparência e finanças",
};

const scopeFieldNames: Record<string, string> = {
  account_label: "Conta",
  active: "Cadastro ativo",
  activity_label: "Atividade",
  annex: "Anexo",
  age_band: "Faixa etária",
  bed_type_label: "Tipo de leito",
  care_type: "Tipo de atenção",
  category_label: "Categoria",
  classification_label: "Classificação",
  column: "Coluna contábil",
  dataset_label: "Conjunto",
  dependency_label: "Dependência",
  facility_type_label: "Tipo de estabelecimento",
  geography_basis: "Base territorial",
  modality: "Modalidade",
  network_label: "Rede",
  price_basis: "Base de preços",
  procedure_label: "Procedimento",
  product_label: "Produto",
  program_label: "Programa",
  power: "Poder",
  reference_period: "Período de referência",
  section_label: "Setor econômico",
  service_label: "Serviço",
  service_type: "Tipo de serviço",
  source_system: "Sistema de origem",
  stage_label: "Etapa",
  statement_type: "Demonstrativo",
  status: "Situação",
  sus_linked: "Vinculado ao SUS",
  sus_sector: "Vínculo SUS",
  transfer_type: "Tipo de transferência",
};

const availabilityNames: Record<string, string> = {
  available: "Publicado",
  unavailable: "Indisponível",
  suppressed: "Suprimido pela fonte",
  not_applicable: "Não se aplica",
};

const indicatorNames: Record<string, string> = {
  "observation:population_estimated": "População estimada",
  "observation:revenue_realized": "Receita realizada",
  "observation:expense_committed": "Despesa empenhada",
  "observation:expense_liquidated": "Despesa liquidada",
  "observation:expense_paid": "Despesa paga",
  "agriculture:production_quantity": "Quantidade produzida",
  "economy:gdp_current_prices": "PIB municipal a preços correntes",
  "economy:gross_value_added": "Valor adicionado bruto",
  "economy:product_taxes_net_subsidies": "Impostos sobre produtos, líquidos de subsídios",
  "education:ideb": "Ideb",
  "education:saeb_mathematics": "Saeb — Matemática",
  "education:enrollment_count": "Matrículas na educação básica",
  "infrastructure:registered_fleet": "Frota de veículos registrada",
  "health_epidemiology:sim_deaths_residence": "Óbitos por local de residência (SIM)",
  "health_epidemiology:sinasc_live_births_residence": "Nascidos vivos por local de residência (Sinasc)",
};

function indicatorLabel(code: string, label: string): string {
  if (indicatorNames[code]) return indicatorNames[code];
  if (!label.includes("_")) return label;
  const normalized = label.replaceAll("_", " ");
  return normalized.charAt(0).toLocaleUpperCase("pt-BR") + normalized.slice(1);
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function scopeLabel(scope: ResearchPoint["scope"]): string {
  const labels = Object.entries(scope)
    .filter(([key, value]) => value !== null && value !== "" && (key.endsWith("_label") || !(`${key}_label` in scope)))
    .map(([key, value]) => `${scopeFieldNames[key] ?? key.replaceAll("_", " ")}: ${typeof value === "boolean" ? (value ? "Sim" : "Não") : String(value)}`);
  return labels.join(" · ") || "Total / sem dimensão adicional";
}

function periodLabel(point: ResearchPoint): string {
  if (point.period_start === point.period_end) return point.period_start;
  return `${point.period_start} a ${point.period_end}`;
}

function ResearchChart({ points, unit }: { points: ResearchPoint[]; unit: string }) {
  const municipalities = [...new Set(points.map((point) => point.geo_name))];
  const chart = [...new Set(points.map((point) => point.period_start))]
    .sort()
    .map((period) => {
      const row: Record<string, string | number | null> = { period };
      for (const name of municipalities) {
        const point = points.find((item) => item.period_start === period && item.geo_name === name);
        row[name] = point?.value === null || point?.value === undefined ? null : Number(point.value);
      }
      return row;
    });
  return (
    <div className="card h-[390px] p-4" aria-label={`Série de ${unit}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chart} margin={{ top: 15, right: 20, left: 15, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1023331c" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={70} tickFormatter={(value) => compactNumber(Number(value))} />
          <Tooltip formatter={(value) => formatValue(value as number, unit)} />
          <Legend />
          {municipalities.map((name, index) => (
            <Line key={name} type="monotone" dataKey={name} connectNulls={false} stroke={COLORS[index % COLORS.length]} strokeWidth={3} dot={{ r: 3 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ComparisonSnapshot({ points, unit }: { points: ResearchPoint[]; unit: string }) {
  const latest = new Map<string, ResearchPoint>();
  for (const point of [...points].sort((left, right) => left.period_end.localeCompare(right.period_end))) {
    latest.set(point.geo_id, point);
  }
  return (
    <section aria-label="Último valor por município" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {[...latest.values()].map((point, index) => (
        <article key={point.geo_id} className="card interactive-card min-w-0 overflow-hidden border-t-4 p-5" style={{ borderTopColor: COLORS[index % COLORS.length] }}>
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink/50">{point.geo_name}/{point.state}</p>
          <p className="mt-3 break-words text-[clamp(1.55rem,2.4vw,2.35rem)] font-black leading-tight text-[#073f35] [overflow-wrap:anywhere]">{formatValue(point.value, unit)}</p>
          <p className="mt-2 text-xs text-ink/50">Última referência no recorte: {periodLabel(point)}</p>
        </article>
      ))}
    </section>
  );
}

function CoverageMap({ geoIds, names }: { geoIds: string[]; names: Record<string, string> }) {
  const [features, setFeatures] = useState<Array<{ code: string; geometry: { type: string; coordinates: unknown } }>>([]);
  useEffect(() => {
    let active = true;
    Promise.all(
      geoIds.map(async (code) => {
        try {
          const feature = await fetchJson<{ geometry: { type: string; coordinates: unknown } }>(`/geo/boundaries/${code}`);
          return { code, geometry: feature.geometry };
        } catch {
          return null;
        }
      }),
    ).then((items) => active && setFeatures(items.filter((item): item is NonNullable<typeof item> => item !== null)));
    return () => { active = false; };
  }, [geoIds.join(",")]);

  const polygons = useMemo(() => {
    const all: Array<{ code: string; ring: number[][] }> = [];
    for (const feature of features) {
      const coords = feature.geometry.coordinates as number[][][][];
      if (feature.geometry.type === "Polygon") all.push({ code: feature.code, ring: (coords as unknown as number[][][])[0] });
      if (feature.geometry.type === "MultiPolygon") for (const polygon of coords) all.push({ code: feature.code, ring: polygon[0] });
    }
    return all;
  }, [features]);
  const flat = polygons.flatMap((item) => item.ring);
  if (!flat.length) return <div className="card p-6 text-sm text-ink/60">Malha oficial ainda não publicada para os municípios selecionados. O mapa não é estimado.</div>;
  const xs = flat.map(([x]) => x); const ys = flat.map(([, y]) => y);
  const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys);
  const width = Math.max(maxX - minX, 0.01); const height = Math.max(maxY - minY, 0.01); const pad = Math.max(width, height) * 0.08;
  return (
    <figure className="card p-5">
      <svg viewBox={`${minX - pad} ${-(maxY + pad)} ${width + pad * 2} ${height + pad * 2}`} className="h-72 w-full" role="img" aria-label="Malhas municipais oficiais do IBGE">
        {polygons.map((item, index) => <path key={`${item.code}-${index}`} d={`${item.ring.map(([x, y], point) => `${point ? "L" : "M"}${x},${-y}`).join(" ")} Z`} fill={`${COLORS[geoIds.indexOf(item.code) % COLORS.length]}55`} stroke={COLORS[geoIds.indexOf(item.code) % COLORS.length]} strokeWidth={width / 450} vectorEffect="non-scaling-stroke" />)}
      </svg>
      <figcaption className="mt-3 text-xs text-ink/60">Malhas oficiais publicadas, sem interpolação. {features.map((feature) => names[feature.code] ?? feature.code).join(" · ")}</figcaption>
    </figure>
  );
}

export function ResearchWorkbench({ compareMode = false }: { compareMode?: boolean }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [dictionary, setDictionary] = useState<ResearchDictionary | null>(null);
  const [series, setSeries] = useState<ResearchSeries | null>(null);
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [savedUrl, setSavedUrl] = useState("");
  const [exportStatus, setExportStatus] = useState("");
  const [municipalitySearch, setMunicipalitySearch] = useState("");
  const indicator = searchParams.get("indicador") ?? (compareMode ? "education:ideb" : "health:production_quantity");
  const geoIds = (searchParams.get("municipios") ?? DEFAULT_GEOS).split(",").filter(Boolean).slice(0, 8);
  const startYear = searchParams.get("inicio") ?? "";
  const endYear = searchParams.get("fim") ?? "";
  const scopeKey = searchParams.get("escopo") ?? "";
  const queryString = searchParams.toString();

  useEffect(() => {
    Promise.all([
      fetchJson<ResearchDictionary>("/research/indicators"),
      fetchJson<Municipality[]>("/municipalities"),
    ]).then(([definitions, places]) => { setDictionary(definitions); setMunicipalities(places); }).catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    const controller = new AbortController(); setSeries(null); setLoading(true); setError("");
    const params = new URLSearchParams({ indicator, geo_ids: geoIds.join(","), limit: "1000" });
    if (startYear) params.set("start_year", startYear); if (endYear) params.set("end_year", endYear); if (scopeKey) params.set("scope_key", scopeKey);
    fetchJson<ResearchSeries>(`/research/series?${params}`, controller.signal).then(setSeries).catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message)).finally(() => setLoading(false));
    return () => controller.abort();
  }, [indicator, geoIds.join(","), startYear, endYear, scopeKey]);

  useEffect(() => {
    if (!compareMode || scopeKey || !series || series.scopes.length <= 1) return;
    const preferred = series.scopes.find((item) => item.scope.network === "municipal" && ["fundamental_early", "fundamental_year_5", "all_basic"].includes(String(item.scope.stage)))
      ?? series.scopes.find((item) => item.scope.network === "municipal")
      ?? [...series.scopes].sort((left, right) => right.rows - left.rows)[0];
    if (!preferred) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("escopo", preferred.scope_key);
    router.replace(`/comparar?${params}`);
  }, [compareMode, scopeKey, series, router, searchParams]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const params = new URLSearchParams();
    params.set("indicador", String(form.get("indicador")));
    const selected = form.getAll("municipios").map(String).slice(0, 8); params.set("municipios", selected.join(","));
    for (const [field, target] of [["inicio", "inicio"], ["fim", "fim"], ["escopo", "escopo"]] as const) { const value = String(form.get(field) ?? ""); if (value) params.set(target, value); }
    router.push(`${compareMode ? "/comparar" : "/pesquisa"}?${params}`);
  }

  const exportParams = new URLSearchParams({ indicator, geo_ids: geoIds.join(",") });
  if (startYear) exportParams.set("start_year", startYear); if (endYear) exportParams.set("end_year", endYear); if (scopeKey) exportParams.set("scope_key", scopeKey);
  const names = Object.fromEntries(municipalities.map((item) => [item.ibge_code, `${item.name}/${item.state}`]));
  const displayed = scopeKey ? series?.items ?? [] : (series?.scopes.length === 1 ? series.items : []);
  const municipalityMatches = municipalities.filter((item) => {
    const needle = municipalitySearch.trim().toLocaleLowerCase("pt-BR");
    return needle && !geoIds.includes(item.ibge_code) && `${item.name} ${item.state} ${item.ibge_code}`.toLocaleLowerCase("pt-BR").includes(needle);
  }).slice(0, 20);
  const selectableIndicators = dictionary?.items.filter((item) => !compareMode || (item.published && item.comparable && item.row_count > 0)) ?? [];

  function updateMunicipalities(next: string[]) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("municipios", next.slice(0, 8).join(","));
    router.push(`${compareMode ? "/comparar" : "/pesquisa"}?${params}`);
  }

  async function saveQuery() {
    const response = await fetch(`${API_BASE}/v1/research/queries`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ indicator, geo_ids: geoIds, ...(startYear && { start_year: Number(startYear) }), ...(endYear && { end_year: Number(endYear) }), ...(scopeKey && { scope_key: scopeKey }) }) });
    if (!response.ok) { setError("Não foi possível salvar a consulta."); return; }
    const payload = await response.json() as { canonical_url: string }; setSavedUrl(`${window.location.origin}${payload.canonical_url}`);
  }

  async function createParquet() {
    setExportStatus("Preparando exportação Parquet…");
    const filters = { indicator, geo_ids: geoIds, ...(startYear && { start_year: Number(startYear) }), ...(endYear && { end_year: Number(endYear) }), ...(scopeKey && { scope_key: scopeKey }) };
    const response = await fetch(`${API_BASE}/v1/export-jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ domain: "research", format: "parquet", filters, row_limit: 250000 }) });
    if (!response.ok) { setExportStatus("Não foi possível iniciar a exportação Parquet."); return; }
    const job = await response.json() as { id: string };
    for (let attempt = 0; attempt < 30; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const check = await fetch(`${API_BASE}/v1/export-jobs/${job.id}`);
      if (!check.ok) break;
      const current = await check.json() as { status: string; download_url: string | null; row_count: number | null };
      if (current.status === "completed" && current.download_url) { setExportStatus(`Pronto: ${current.row_count?.toLocaleString("pt-BR") ?? ""} linhas`); window.location.assign(current.download_url); return; }
      if (current.status === "failed") { setExportStatus("A exportação falhou; consulte o estado do job na API."); return; }
    }
    setExportStatus(`Exportação em processamento. Job ${job.id}.`);
  }

  return (
    <div className="grid gap-8">
      {dictionary && !compareMode && <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(dictionary.domains).map(([domain, totals]) => <div className="card p-4" key={domain}><p className="text-sm font-extrabold">{domainNames[domain] ?? domain}</p><p className="mt-1 text-2xl font-black">{totals.rows.toLocaleString("pt-BR")}</p><p className="text-xs text-ink/55">linhas · {totals.published}/{totals.indicators} indicadores publicados</p></div>)}</section>}
      {compareMode && <section className="rounded-[1.5rem] border border-teal/20 bg-teal/5 p-5"><p className="text-sm font-bold text-[#087875]">Comparações rápidas</p><div className="mt-3 flex flex-wrap gap-2">{[
        ["Ideb", "education:ideb"],
        ["Matrículas", "education:enrollment_count"],
        ["Saeb — Matemática", "education:saeb_mathematics"],
        ["PIB municipal", "economy:gdp_current_prices"],
      ].map(([label, code]) => <Link key={code} href={`/comparar?indicador=${encodeURIComponent(code)}&municipios=${geoIds.join(",")}`} className={`rounded-full px-4 py-2 text-sm font-bold transition ${indicator === code ? "bg-[#073f35] text-white shadow-md" : "border border-ink/15 bg-white hover:-translate-y-0.5 hover:border-teal hover:text-teal"}`}>{label}</Link>)}</div></section>}
      <form onSubmit={submit} className="card grid gap-5 p-6 lg:grid-cols-2">
        <label className="text-sm font-bold">Indicador
          <select name="indicador" value={indicator} onChange={(event) => router.push(`${compareMode ? "/comparar" : "/pesquisa"}?indicador=${encodeURIComponent(event.target.value)}&municipios=${geoIds.join(",")}`)} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal">
            {dictionary && Object.entries(Object.groupBy(selectableIndicators, (item) => item.domain)).map(([domain, items]) => <optgroup key={domain} label={domainNames[domain] ?? domain}>{items?.map((item) => <option key={item.code} value={item.code}>{indicatorLabel(item.code, item.label)} ({item.row_count.toLocaleString("pt-BR")}){item.published ? "" : " — sem linhas"}</option>)}</optgroup>)}
          </select>
        </label>
        <fieldset>
          <legend className="text-sm font-bold">Municípios para comparar (até 8)</legend>
          {geoIds.map((code) => <input key={code} type="hidden" name="municipios" value={code} />)}
          <div className="mt-2 flex min-h-12 flex-wrap gap-2 rounded-xl border border-ink/20 bg-white p-2">
            {geoIds.map((code) => <span key={code} className="inline-flex items-center gap-2 rounded-lg bg-mist px-3 py-2 text-sm font-bold">{names[code] ?? code}<button type="button" disabled={geoIds.length === 1} aria-label={`Remover ${names[code] ?? code}`} onClick={() => updateMunicipalities(geoIds.filter((item) => item !== code))} className="text-ink/45 hover:text-ink disabled:cursor-not-allowed disabled:opacity-30">×</button></span>)}
          </div>
          <input value={municipalitySearch} onChange={(event) => setMunicipalitySearch(event.target.value)} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="Digite nome, UF ou código IBGE" />
          {municipalityMatches.length > 0 && <select aria-label="Adicionar município" value="" onChange={(event) => { if (event.target.value) updateMunicipalities([...geoIds, event.target.value]); setMunicipalitySearch(""); }} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 text-sm"><option value="">Selecione para adicionar</option>{municipalityMatches.map((item) => <option key={item.ibge_code} value={item.ibge_code}>{item.name}/{item.state} · {item.ibge_code}</option>)}</select>}
        </fieldset>
        <div className="grid grid-cols-2 gap-3"><label className="text-sm font-bold">Ano inicial<input name="inicio" type="number" min="1900" max="2100" defaultValue={startYear} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label><label className="text-sm font-bold">Ano final<input name="fim" type="number" min="1900" max="2100" defaultValue={endYear} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label></div>
        <label className="text-sm font-bold">Escopo comparável<select name="escopo" key={`${indicator}-${scopeKey}-${series?.scopes.length ?? 0}`} defaultValue={scopeKey} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Escolha quando houver dimensões</option>{series?.scopes.map((scope) => <option key={scope.scope_key} value={scope.scope_key}>{scopeLabel(scope.scope)} ({scope.rows})</option>)}</select></label>
        <div className="flex flex-wrap items-end gap-3 lg:col-span-2"><button className="button-primary">Visualizar recorte</button><button type="button" onClick={saveQuery} className="button-secondary">Salvar link reproduzível</button><Link href="/buscar" className="button-secondary">Auditar catálogo</Link></div>
        {savedUrl && <output className="rounded-xl bg-mist p-3 text-sm lg:col-span-2"><strong>Link:</strong> <a className="text-teal underline" href={savedUrl}>{savedUrl}</a></output>}
      </form>
      {error && <ErrorState message={error} />}{loading && <LoadingState label="Consultando fatos, escopos e proveniência…" />}
      {!loading && series && <>
        <section className="card p-6"><p className="eyebrow">{domainNames[series.definition.domain] ?? series.definition.domain}</p><div className="mt-2 flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-3xl font-black">{series.definition.label}</h2><p className="mt-2 text-sm text-ink/60">{series.count.toLocaleString("pt-BR")} linhas no recorte · {series.definition.unit} · {series.definition.periodicity}</p></div><div className="flex flex-wrap gap-2"><a className="button-secondary" href={`${API_BASE}/v1/research/export.csv?${exportParams}`}>CSV</a><a className="button-secondary" href={`${API_BASE}/v1/research/export.json?${exportParams}`}>JSON</a><button type="button" onClick={createParquet} className="button-secondary">Parquet</button></div></div>{exportStatus && <p className="mt-3 text-xs font-bold text-teal">{exportStatus}</p>}<p className="mt-5 text-sm leading-6"><strong>Método:</strong> {series.definition.methodology}</p><p className="mt-2 text-sm leading-6 text-ink/65"><strong>Limites:</strong> {series.definition.limitations}</p></section>
        {series.definition.scope_required && !scopeKey && series.scopes.length > 1 ? <section className="rounded-2xl border border-gold/60 bg-gold/10 p-6"><h2 className="font-extrabold">Escolha um escopo antes de comparar ou desenhar a série</h2><p className="mt-2 text-sm">Existem {series.scopes.length} categorias diferentes. Selecione uma opção no campo “Escopo comparável” acima; misturar categorias poderia duplicar ou distorcer o indicador.</p></section> : displayed.length ? <><ComparisonSnapshot points={displayed} unit={series.definition.unit} /><ResearchChart points={displayed} unit={series.definition.unit} /></> : <section className="card p-6">Nenhuma linha publicada neste recorte. Indisponível não é zero.</section>}
        <CoverageMap geoIds={geoIds} names={names} />
        <section className="overflow-hidden rounded-2xl border border-ink/10 bg-white"><div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="bg-ink text-white"><tr><th className="p-3">Território</th><th className="p-3">Período</th><th className="p-3">Escopo</th><th className="p-3">Valor</th><th className="p-3">Fonte</th><th className="p-3">Estado</th></tr></thead><tbody>{series.items.map((point, index) => <tr key={`${point.geo_id}-${point.period_start}-${point.scope_key}-${index}`} className="border-t border-ink/10 align-top"><td className="p-3 font-bold">{point.geo_name}/{point.state}</td><td className="whitespace-nowrap p-3">{periodLabel(point)}</td><td className="max-w-sm p-3 text-xs">{scopeLabel(point.scope)}</td><td className="whitespace-nowrap p-3 font-bold">{formatValue(point.value, point.unit)}</td><td className="p-3"><a href={point.source_url} target="_blank" rel="noreferrer" className="font-bold text-teal hover:underline">{point.provider}</a><span className="block text-xs text-ink/50">{point.dataset} · rev. {point.revision}</span></td><td className="p-3">{availabilityNames[point.availability_status] ?? point.availability_status.replaceAll("_", " ")}</td></tr>)}</tbody></table></div>{series.count > series.items.length && <p className="border-t border-ink/10 p-4 text-xs text-ink/60">Mostrando {series.items.length} de {series.count.toLocaleString("pt-BR")} linhas. Use CSV/JSON para até 10 mil linhas; exportações maiores usam o serviço assíncrono.</p>}</section>
      </>}
    </div>
  );
}
