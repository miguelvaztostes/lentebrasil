"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";
import { fetchJson, type MunicipalitySummary } from "@/lib/api";

const sectorLabels: Record<string, string> = {
  "agropecuaria-e-rural": "Agropecuária e rural",
  desenvolvimento: "Desenvolvimento",
  "economia-e-trabalho": "Economia e trabalho",
  educacao: "Educação",
  "financas-publicas": "Finanças públicas",
  "infraestrutura-e-cidades": "Infraestrutura e cidades",
  saude: "Saúde",
  "territorio-e-demografia": "Território e demografia",
};

export function Dashboard({ municipalityCode = "3543402" }: { municipalityCode?: string }) {
  const [data, setData] = useState<MunicipalitySummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<MunicipalitySummary>(`/municipios/${encodeURIComponent(municipalityCode)}/summary`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [municipalityCode]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  return (
    <div>
      {data.cards.length ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {data.cards.map((card) => <DataCard key={card.indicator.code} indicator={card.indicator} observation={card} municipalityCode={municipalityCode} />)}
        </div>
      ) : (
        <div className="card p-8">
          <p className="font-bold">O catálogo está pronto, mas ainda não há observações validadas.</p>
          <p className="mt-2 text-sm text-ink/65">Execute o coletor oficial. A interface não exibirá números fictícios enquanto isso.</p>
        </div>
      )}
      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {data.sectors.filter((sector) => sector.published_datasets > 0).map((sector) => (
          <Link href={`/municipios/${municipalityCode}/${sector.slug}`} key={sector.slug} className="card interactive-card group p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-black">{sectorLabels[sector.slug] ?? sector.slug.replaceAll("-", " ")}</span>
              <StatusBadge status={sector.published_datasets ? "published" : "discovered"} />
            </div>
            <p className="mt-5 text-3xl font-black text-[#073f35]">{sector.published_datasets}</p>
            <p className="mt-1 text-xs text-ink/55">conjunto{sector.published_datasets === 1 ? "" : "s"} publicado{sector.published_datasets === 1 ? "" : "s"}</p>
          </Link>
        ))}
      </div>
      <div className="mt-7 text-right"><Link href={`/municipios/${municipalityCode}`} className="text-sm font-bold text-teal hover:underline">Ver todos os temas e fontes →</Link></div>
    </div>
  );
}

