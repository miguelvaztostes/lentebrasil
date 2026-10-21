"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";
import { fetchJson, type MunicipalitySummary } from "@/lib/api";

export function MunicipalityProfile({ code }: { code: string }) {
  const [data, setData] = useState<MunicipalitySummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<MunicipalitySummary>(`/municipios/${encodeURIComponent(code)}/summary`, controller.signal).then(setData).catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Carregando perfil municipal…" />;
  return <div>
    <p className="eyebrow">{data.municipality.state} · código IBGE {data.municipality.ibge_code}</p>
    <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">{data.municipality.name}</h1>
    <p className="mt-5 max-w-3xl text-lg leading-8 text-ink/65">Perfil público municipal. Coleta e período de referência aparecem separados em cada indicador.</p>
    <section className="mt-12" aria-labelledby="available-title"><h2 id="available-title" className="text-2xl font-black">Dados homologados disponíveis</h2>{data.available_indicators.length ? <div className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{data.available_indicators.map((card) => <DataCard key={card.indicator.code} indicator={card.indicator} observation={card} municipalityCode={code} />)}</div> : <div className="card mt-6 p-8"><p className="font-bold">Ainda não há observações publicadas para este município.</p><p className="mt-2 text-sm text-ink/65">O município existe no diretório oficial, mas nenhum número será inventado ou substituído por zero.</p></div>}</section>
    <section className="mt-16" aria-labelledby="sector-title"><div className="flex flex-wrap items-end justify-between gap-4"><div><h2 id="sector-title" className="text-2xl font-black">Setores e fontes identificadas</h2><p className="mt-2 text-sm text-ink/60">Disponibilidade efetiva e fontes candidatas são contagens diferentes.</p></div><Link href="/fontes" className="text-sm font-bold text-teal hover:underline">Consultar catálogo nacional →</Link></div><div className="mt-6 grid gap-4 md:grid-cols-3">{data.sectors.map((sector) => <Link href={`/municipios/${code}/${sector.slug}`} key={sector.slug} className="card p-5 transition hover:border-teal"><div className="flex items-start justify-between gap-3"><h3 className="font-extrabold">{sector.slug.replaceAll("-", " ")}</h3><StatusBadge status={sector.published_datasets ? "published" : "discovered"} /></div><p className="mt-4 text-sm"><strong>{sector.published_datasets}</strong> recurso(s) publicado(s)</p><p className="mt-1 text-sm text-ink/55"><strong>{sector.candidate_sources}</strong> fonte(s) candidata(s)</p></Link>)}</div></section>
  </div>;
}
