"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { fetchJson, type MunicipalitySummary } from "@/lib/api";
import { EducationDashboard } from "./EducationDashboard";
import { HealthDashboard } from "./HealthDashboard";
import { TransparencyDashboard } from "./TransparencyDashboard";
import { SectorDashboard } from "./SectorDashboard";

export function MunicipalitySector({ code, sector }: { code: string; sector: string }) {
  if (sector === "educacao") return <EducationDashboard code={code} />;
  if (sector === "saude") return <HealthDashboard code={code} />;
  if (sector === "financas-publicas" || sector === "transparencia") return <TransparencyDashboard municipalityCode={code} />;
  if (["economia-e-trabalho", "trabalho", "protecao-social", "infraestrutura-e-cidades", "infraestrutura"].includes(sector)) return <SectorDashboard code={code} sector={sector} />;
  return <GenericMunicipalitySector code={code} sector={sector} />;
}

function GenericMunicipalitySector({ code, sector }: { code: string; sector: string }) {
  const [data, setData] = useState<MunicipalitySummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchJson<MunicipalitySummary>(`/municipios/${encodeURIComponent(code)}/summary`).then(setData).catch((reason: Error) => setError(reason.message));
  }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  const available = data.available_indicators.filter((item) => item.indicator.domain === sector);
  const catalog = data.sectors.find((item) => item.slug === sector);
  return <div><p className="eyebrow">{data.municipality.name}/{data.municipality.state}</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">{sector.replaceAll("-", " ")}</h1><p className="mt-5 text-ink/65">Dados publicados aparecem primeiro; fontes ainda não integradas permanecem apenas como informação de catálogo.</p>{available.length ? <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{available.map((item) => <DataCard key={item.indicator.code} indicator={item.indicator} observation={item} municipalityCode={code} />)}</div> : <div className="card mt-10 p-8"><h2 className="text-xl font-extrabold">Nenhum dado homologado neste setor</h2><p className="mt-3 text-sm text-ink/65">Há {catalog?.candidate_sources ?? 0} fonte(s) candidata(s) catalogada(s), mas isso não comprova cobertura para este município.</p></div>}<div className="mt-8 flex gap-4"><Link href={`/buscar?sector=${encodeURIComponent(sector)}`} className="button-primary">Ver fontes candidatas</Link><Link href={`/municipios/${code}`} className="button-secondary">Voltar ao município</Link></div></div>;
}
