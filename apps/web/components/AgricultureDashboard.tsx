"use client";

import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { useEffect, useMemo, useState } from "react";
import { ErrorState, LoadingState } from "./LoadingState";
import { fetchJson, type AgricultureResponse } from "@/lib/api";

const metricLabels: Record<string, { label: string; short: string }> = {
  production_quantity: { label: "Quantidade produzida", short: "Produção" },
  planted_area: { label: "Área plantada ou destinada à colheita", short: "Área plantada" },
  harvested_area: { label: "Área colhida", short: "Área colhida" },
  average_yield: { label: "Rendimento médio da produção", short: "Rendimento" },
  production_value: { label: "Valor da produção", short: "Valor produzido" },
};

const metricOrder = ["production_quantity", "production_value", "planted_area", "harvested_area", "average_yield"];

function formatAgricultureValue(value: string, unit: string) {
  const formatted = Number(value).toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  return unit === "Mil Reais" ? `R$ ${formatted} mil` : formatted;
}

export function AgricultureDashboard({ code }: { code: string }) {
  const [data, setData] = useState<AgricultureResponse | null>(null);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState("production_quantity");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<AgricultureResponse>(`/sectors/agriculture?municipality=${encodeURIComponent(code)}&limit=1000`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [code]);

  const metrics = useMemo(() => {
    const available = new Set(data?.items.map((item) => item.metric) ?? []);
    return metricOrder.filter((item) => available.has(item));
  }, [data]);

  useEffect(() => {
    if (metrics.length && !metrics.includes(metric)) setMetric(metrics[0]);
  }, [metric, metrics]);

  const rows = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLocaleLowerCase("pt-BR");
    return data.items
      .filter((item) => item.metric === metric && item.value !== null && item.product.code !== "0")
      .filter((item) => !needle || item.product.name.toLocaleLowerCase("pt-BR").includes(needle))
      .sort((left, right) => Number(right.value) - Number(left.value));
  }, [data, metric, query]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  const shown = expanded ? rows : rows.slice(0, 12);
  const leader = rows[0];
  const unavailable = data.items.filter((item) => item.metric === metric && item.value === null).length;
  const source = data.items[0]?.source;

  return (
    <div>
      <p className="eyebrow">Agropecuária e rural</p>
      <h1 className="mt-3 max-w-5xl text-4xl font-black tracking-tight sm:text-6xl">Produção agrícola de Ribeirão Preto</h1>
      <p className="mt-3 text-sm font-bold text-[#657b3d]">Quantidade produzida — PAM 2024</p>
      <p className="mt-5 max-w-3xl leading-7 text-ink/65">
        PAM/IBGE 2024 por produto, com cinco leituras oficiais mantidas separadas. Na fonte, a ausência continua indisponível e nunca vira zero.
      </p>

      <nav aria-label="Métricas agrícolas" className="mt-8 flex flex-wrap gap-2">
        {metrics.map((item) => (
          <button key={item} type="button" onClick={() => { setMetric(item); setExpanded(false); }} className={`rounded-full px-4 py-2.5 text-sm font-bold transition ${metric === item ? "bg-[#073f35] text-white shadow-lg" : "border border-ink/15 bg-white hover:-translate-y-0.5 hover:border-[#657b3d] hover:text-[#657b3d]"}`}>
            {metricLabels[item]?.short ?? item.replaceAll("_", " ")}
          </button>
        ))}
      </nav>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl bg-[#657b3d] p-6 text-white shadow-lg"><p className="text-xs font-bold uppercase tracking-[0.14em] text-white/65">Métrica selecionada</p><p className="mt-3 text-2xl font-black">{metricLabels[metric]?.label ?? metric}</p></article>
        <article className="card p-6"><p className="text-xs font-bold uppercase tracking-[0.14em] text-ink/45">Produtos publicados</p><p className="mt-3 text-4xl font-black text-[#073f35]">{rows.length}</p><p className="mt-1 text-xs text-ink/50">{unavailable} produtos sem valor na fonte</p></article>
        <article className="card min-w-0 overflow-hidden p-6"><p className="text-xs font-bold uppercase tracking-[0.14em] text-ink/45">Maior valor do recorte</p><p className="mt-3 truncate text-xl font-black text-[#073f35]">{leader?.product.name ?? "Indisponível"}</p><p className="mt-1 break-words text-sm font-bold text-[#657b3d]">{leader?.value ? formatAgricultureValue(leader.value, leader.unit) : "—"} {leader && leader.unit !== "Mil Reais" ? leader.unit : ""}</p></article>
      </section>

      <section className="mt-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div><p className="eyebrow">Produtos com valor publicado</p><h2 className="mt-2 text-3xl font-black">{metricLabels[metric]?.label}</h2></div>
          <label className="relative block w-full max-w-sm"><span className="sr-only">Buscar produto</span><MagnifyingGlassIcon className="pointer-events-none absolute left-4 top-3.5 h-5 w-5 text-ink/35" /><input value={query} onChange={(event) => { setQuery(event.target.value); setExpanded(true); }} className="w-full rounded-xl border border-ink/15 bg-white py-3 pl-11 pr-4 text-sm outline-none transition focus:border-teal focus:ring-2 focus:ring-teal/15" placeholder="Buscar cultura ou produto" /></label>
        </div>
        {shown.length ? <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{shown.map((item, index) => <article className="card interactive-card relative overflow-hidden border-t-4 border-t-[#657b3d] p-6" key={`${item.metric}-${item.year}-${item.product.code}`}><span className="absolute right-5 top-4 text-xs font-black text-ink/20">{String(index + 1).padStart(2, "0")}</span><p className="eyebrow">{item.year} · IBGE</p><h3 className="mt-2 pr-8 text-lg font-extrabold">{item.product.name}</h3><p className="mt-5 break-words text-3xl font-black leading-tight text-[#073f35]">{formatAgricultureValue(item.value!, item.unit)}</p><p className="mt-1 text-xs text-ink/55">{item.unit === "Mil Reais" ? "valor nominal publicado em milhares de reais" : item.unit}</p></article>)}</div> : <article className="card mt-6 p-8"><h2 className="text-xl font-extrabold">Nenhum produto encontrado</h2><p className="mt-3 text-sm text-ink/65">Tente outro termo ou escolha uma métrica diferente.</p></article>}
        {rows.length > 12 && !query ? <div className="mt-7 text-center"><button type="button" onClick={() => setExpanded((value) => !value)} className="button-secondary">{expanded ? "Mostrar menos" : `Ver todos os ${rows.length} produtos publicados`}</button></div> : null}
      </section>

      <details className="card mt-10 p-6"><summary className="cursor-pointer font-extrabold">Metodologia e proveniência</summary><p className="mt-4 text-sm leading-6 text-ink/65">{data.methodology}</p>{source ? <div className="mt-4 text-sm"><p><strong>Período:</strong> 2024</p><p><strong>Dataset:</strong> {source.dataset}</p><p><strong>Licença/status:</strong> {source.license ?? "Atribuição ao IBGE"} · {source.publication_status}</p><a className="font-bold text-teal underline" href={source.url} target="_blank" rel="noreferrer">Abrir resposta oficial versionada</a></div> : null}</details>
    </div>
  );
}
