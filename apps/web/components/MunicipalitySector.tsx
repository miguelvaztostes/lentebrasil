"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { fetchJson, type InventoryMatrix, type MunicipalitySummary } from "@/lib/api";
import { EducationDashboard } from "./EducationDashboard";
import { HealthDashboard } from "./HealthDashboard";
import { TransparencyDashboard } from "./TransparencyDashboard";
import { SectorDashboard } from "./SectorDashboard";
import { AgricultureDashboard } from "./AgricultureDashboard";

export function MunicipalitySector({ code, sector }: { code: string; sector: string }) {
  if (sector === "educacao") return <EducationDashboard code={code} />;
  if (sector === "saude") return <HealthDashboard code={code} />;
  if (sector === "financas-publicas" || sector === "transparencia") return <TransparencyDashboard municipalityCode={code} />;
  if (["economia-e-trabalho", "trabalho", "protecao-social", "infraestrutura-e-cidades", "infraestrutura"].includes(sector)) return <SectorDashboard code={code} sector={sector} />;
  if (sector === "agropecuaria-e-rural") return <AgricultureDashboard code={code} />;
  return <GenericMunicipalitySector code={code} sector={sector} />;
}

function GenericMunicipalitySector({ code, sector }: { code: string; sector: string }) {
  const [data, setData] = useState<MunicipalitySummary | null>(null);
  const [matrix, setMatrix] = useState<InventoryMatrix | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      fetchJson<MunicipalitySummary>(`/municipios/${encodeURIComponent(code)}/summary`),
      fetchJson<InventoryMatrix>(`/catalog/matrix?area=${encodeURIComponent(sector)}&limit=200`),
    ]).then(([summary, inventory]) => { setData(summary); setMatrix(inventory); }).catch((reason: Error) => setError(reason.message));
  }, [code, sector]);
  if (error) return <ErrorState message={error} />;
  if (!data || !matrix) return <LoadingState />;
  const available = data.available_indicators.filter((item) => item.indicator.domain === sector);
  const catalog = data.sectors.find((item) => item.slug === sector);
  return <div><p className="eyebrow">{data.municipality.name}/{data.municipality.state}</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">{sector.replaceAll("-", " ")}</h1><p className="mt-5 text-ink/65">Dados publicados aparecem primeiro; fontes ainda não integradas permanecem visíveis com decisão e bloqueio.</p>{available.length ? <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{available.map((item) => <DataCard key={item.indicator.code} indicator={item.indicator} observation={item} municipalityCode={code} />)}</div> : <div className="card mt-10 p-8"><h2 className="text-xl font-extrabold">Nenhum dado homologado neste setor</h2><p className="mt-3 text-sm text-ink/65">Há {catalog?.candidate_sources ?? matrix.count} fonte(s) candidata(s), mas isso não comprova cobertura para este município.</p></div>}<section className="mt-10"><h2 className="text-2xl font-black">Matriz de fontes do setor</h2><div className="mt-5 grid gap-4 md:grid-cols-2">{matrix.items.map((item) => <article className="card p-5" key={item.id}><div className="flex justify-between gap-3"><strong>{item.id}</strong><span className="eyebrow">{item.review_status}</span></div><h3 className="mt-2 font-extrabold">{item.title}</h3><p className="mt-2 text-sm text-ink/60">{item.blocking_reason ?? "Recurso em revisão técnica."}</p><p className="mt-3 text-xs text-ink/50">Responsável: {item.technical_owner} · recorte declarado: {item.geography ?? "a revisar"}</p>{item.resource_url ? <a className="mt-3 inline-block text-sm font-bold text-teal underline" href={item.resource_url} target="_blank" rel="noreferrer">Fonte catalogada</a> : null}</article>)}</div></section><div className="mt-8 flex gap-4"><Link href={`/buscar?sector=${encodeURIComponent(sector)}`} className="button-primary">Ver fontes candidatas</Link><Link href={`/municipios/${code}`} className="button-secondary">Voltar ao município</Link></div></div>;
}
