"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownTrayIcon, ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { API_BASE, fetchJson, formatDate, formatValue, type IndicatorResponse } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";
import { IndicatorChart } from "./IndicatorChart";
import { StatusBadge } from "./StatusBadge";

export function IndicatorDetail({ code }: { code: string }) {
  const [data, setData] = useState<IndicatorResponse | null>(null);
  const [error, setError] = useState("");
  const [fromYear, setFromYear] = useState("");
  const [toYear, setToYear] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<IndicatorResponse>(`/indicators/${encodeURIComponent(code)}/observations`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [code]);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.items.filter((item) => {
      const year = new Date(item.period_end).getUTCFullYear();
      return (!fromYear || year >= Number(fromYear)) && (!toYear || year <= Number(toYear));
    });
  }, [data, fromYear, toYear]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  const latest = filtered.at(-1);
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="eyebrow">{data.indicator.domain}</p>
          <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">{data.indicator.label}</h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-ink/70">{data.indicator.definition}</p>
        </div>
        <a href={`${API_BASE}/v1/exports/observations.csv?indicator=${encodeURIComponent(code)}`} className="button-secondary gap-2">
          <ArrowDownTrayIcon className="h-5 w-5" /> Baixar CSV
        </a>
      </div>
      <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_320px]">
        <section className="card p-5 sm:p-8" aria-labelledby="serie-title">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 id="serie-title" className="text-xl font-extrabold">Série histórica</h2>
              <p className="text-sm text-ink/60">{data.indicator.unit} · Ribeirão Preto</p>
            </div>
            <div className="flex gap-3">
              <label className="text-xs font-bold">De<input aria-label="Ano inicial" inputMode="numeric" value={fromYear} onChange={(event) => setFromYear(event.target.value.replace(/\D/g, "").slice(0, 4))} className="mt-1 block w-24 rounded-lg border border-ink/20 px-3 py-2 text-sm" placeholder="ano" /></label>
              <label className="text-xs font-bold">Até<input aria-label="Ano final" inputMode="numeric" value={toYear} onChange={(event) => setToYear(event.target.value.replace(/\D/g, "").slice(0, 4))} className="mt-1 block w-24 rounded-lg border border-ink/20 px-3 py-2 text-sm" placeholder="ano" /></label>
            </div>
          </div>
          <div className="mt-7"><IndicatorChart items={filtered} unit={data.indicator.unit} /></div>
          <div className="mt-8 overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <caption className="sr-only">Valores por período, estado, revisão e coleta</caption>
              <thead><tr className="border-b-2 border-ink"><th className="py-3">Período</th><th>Valor</th><th>Estado</th><th>Revisão</th><th>Coleta</th></tr></thead>
              <tbody>{filtered.map((item) => (
                <tr key={`${item.period_end}-${JSON.stringify(item.scope)}`} className="border-b border-ink/10">
                  <td className="py-4 font-bold">{new Date(item.period_end).getUTCFullYear()}</td>
                  <td>{formatValue(item.value, data.indicator.unit)}</td>
                  <td><StatusBadge status={item.availability_status} /></td>
                  <td>{item.revision}</td>
                  <td>{formatDate(item.retrieved_at)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
        <aside className="space-y-5">
          {latest && <div className="rounded-2xl bg-ink p-6 text-white"><p className="text-xs font-bold uppercase tracking-wider text-gold">Último valor filtrado</p><p className="mt-3 text-3xl font-black">{formatValue(latest.value, data.indicator.unit)}</p><p className="mt-2 text-sm text-white/65">Referência {new Date(latest.period_end).getUTCFullYear()}</p></div>}
          <div className="card p-6"><h2 className="font-extrabold">Metodologia</h2><p className="mt-3 text-sm leading-6 text-ink/70">{data.indicator.methodology}</p></div>
          <div className="card p-6"><h2 className="font-extrabold">Limitações</h2><p className="mt-3 text-sm leading-6 text-ink/70">{data.indicator.limitations}</p></div>
          {latest && <div className="card p-6"><h2 className="font-extrabold">Fonte</h2><a href={latest.source.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm font-bold text-teal hover:underline">{latest.source.provider}<ArrowTopRightOnSquareIcon className="h-4 w-4" /></a><p className="mt-3 break-all font-mono text-[10px] text-ink/45">SHA-256 {latest.source.sha256}</p></div>}
        </aside>
      </div>
    </div>
  );
}

