"use client";

import { useEffect, useState } from "react";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";
import { fetchJson, type Indicator, type Observation } from "@/lib/api";

type Summary = {
  municipality: { ibge_code: string; name: string; state: string };
  generated_at: string;
  cards: Array<Observation & { indicator: Indicator }>;
  datasets: Array<{ code: string; title: string; domain: string; status: string }>;
};

export function Dashboard({ municipalityCode = "3543402" }: { municipalityCode?: string }) {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<Summary>(`/municipios/${encodeURIComponent(municipalityCode)}/summary`, controller.signal)
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
          {data.cards.map((card) => <DataCard key={card.indicator.code} indicator={card.indicator} observation={card} />)}
        </div>
      ) : (
        <div className="card p-8">
          <p className="font-bold">O catálogo está pronto, mas ainda não há observações validadas.</p>
          <p className="mt-2 text-sm text-ink/65">Execute o coletor oficial. A interface não exibirá números fictícios enquanto isso.</p>
        </div>
      )}
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {data.datasets.map((dataset) => (
          <div key={dataset.code} className="rounded-xl border border-ink/10 bg-white/70 p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="eyebrow">{dataset.domain}</span>
              <StatusBadge status={dataset.status} />
            </div>
            <p className="mt-3 text-sm font-bold">{dataset.title}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

