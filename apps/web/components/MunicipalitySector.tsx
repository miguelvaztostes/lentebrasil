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
import { SectorIcon } from "./SectorIcon";

const sectorLabels: Record<string, string> = {
  "catalogos-e-descoberta": "Catálogos e descoberta",
  "ciencia-e-inovacao": "Ciência e inovação",
  "cultura-e-turismo": "Cultura e turismo",
  "gestao-publica": "Gestão pública",
  "meio-ambiente-e-riscos": "Meio ambiente e riscos",
  "municipal-ribeirao-preto": "Dados locais de Ribeirão Preto",
  "participacao-e-democracia": "Participação e democracia",
  "protecao-social": "Proteção social",
  "seguranca-publica": "Segurança pública",
};

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
  const context = data.cards.slice(0, 3);
  const title = sectorLabels[sector] ?? sector.replaceAll("-", " ").replace(/^./, (letter) => letter.toLocaleUpperCase("pt-BR"));
  return <div><div className="flex items-center gap-4"><span className="rounded-2xl bg-teal/10 p-3 text-teal"><SectorIcon slug={sector} className="h-8 w-8" /></span><div><p className="eyebrow">{data.municipality.name}/{data.municipality.state}</p><h1 className="mt-2 text-4xl font-black tracking-tight sm:text-6xl">{title}</h1></div></div><p className="mt-5 max-w-3xl text-ink/65">Dados temáticos homologados aparecem primeiro. Fontes ainda não integradas permanecem visíveis com decisão, bloqueio e recorte declarado.</p>{available.length ? <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{available.map((item) => <DataCard key={item.indicator.code} indicator={item.indicator} observation={item} municipalityCode={code} />)}</div> : <><div className="mt-10 rounded-2xl border border-gold/50 bg-gold/10 p-7"><h2 className="text-xl font-extrabold">Tema em implantação</h2><p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">Há {catalog?.candidate_sources ?? matrix.count} fonte(s) candidata(s), mas ainda não existe conjunto temático homologado para este município. Isso significa “indisponível”, não valor zero.</p></div>{context.length ? <section className="mt-10"><p className="eyebrow">Contexto municipal já publicado</p><h2 className="mt-2 text-2xl font-black">Indicadores relacionados de Ribeirão Preto</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-ink/60">Estes cartões ajudam a contextualizar o município, mas não contam como cobertura específica de {title.toLocaleLowerCase("pt-BR")}.</p><div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{context.map((item) => <DataCard key={item.indicator.code} indicator={item.indicator} observation={item} municipalityCode={code} />)}</div></section> : null}</>}<section className="mt-10"><h2 className="text-2xl font-black">Matriz de fontes do setor</h2><div className="mt-5 grid gap-4 md:grid-cols-2">{matrix.items.map((item) => <article className="card p-5" key={item.id}><div className="flex justify-between gap-3"><strong>{item.id}</strong><span className="eyebrow">{item.review_status}</span></div><h3 className="mt-2 font-extrabold">{item.title}</h3><p className="mt-2 text-sm text-ink/60">{item.blocking_reason ?? "Recurso em revisão técnica."}</p><p className="mt-3 text-xs text-ink/50">Responsável: {item.technical_owner} · recorte declarado: {item.geography ?? "a revisar"}</p>{item.resource_url ? <a className="mt-3 inline-block text-sm font-bold text-teal underline" href={item.resource_url} target="_blank" rel="noreferrer">Fonte catalogada</a> : null}</article>)}</div></section><div className="mt-8 flex flex-wrap gap-4"><Link href={`/buscar?sector=${encodeURIComponent(sector)}`} className="button-primary">Ver fontes candidatas</Link><Link href={`/municipios/${code}`} className="button-secondary">Voltar ao município</Link></div></div>;
}
