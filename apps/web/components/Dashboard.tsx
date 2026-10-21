"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";
import { fetchJson, type MunicipalitySummary } from "@/lib/api";

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
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {data.sectors.map((sector) => (
          <Link href={`/municipios/${municipalityCode}/${sector.slug}`} key={sector.slug} className="rounded-xl border border-ink/10 bg-white/70 p-5 transition hover:border-teal">
            <div className="flex items-center justify-between gap-3">
              <span className="eyebrow">{sector.slug}</span>
              <StatusBadge status={sector.published_datasets ? "published" : "discovered"} />
            </div>
            <p className="mt-3 text-sm font-bold">{sector.published_datasets} conjunto(s) publicado(s)</p>
            <p className="mt-1 text-xs text-ink/55">{sector.candidate_sources} fonte(s) candidata(s) no catálogo</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

