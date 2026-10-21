"use client";

import { useEffect, useState } from "react";
import { fetchJson, type IndicatorResponse } from "@/lib/api";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";

export function DomainDashboard({ codes, municipalityCode = "3543402" }: { codes: string[]; municipalityCode?: string }) {
  const [items, setItems] = useState<IndicatorResponse[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all(codes.map((code) => fetchJson<IndicatorResponse>(`/indicators/${code}/observations?municipality=${encodeURIComponent(municipalityCode)}`)))
      .then(setItems).catch((reason: Error) => setError(reason.message));
  }, [codes, municipalityCode]);
  if (error) return <ErrorState message={error} />;
  if (!items) return <LoadingState />;
  const available = items.filter((item) => item.items.length > 0);
  if (!available.length) return <div className="card p-7"><p className="font-bold">Nenhum valor validado nesta área.</p><p className="mt-2 text-sm text-ink/65">O catálogo existe, mas a interface não substitui dados ausentes por zero ou estimativa.</p></div>;
  return <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{available.map((item) => <DataCard key={item.indicator.code} indicator={item.indicator} observation={item.items.at(-1)!} municipalityCode={municipalityCode} />)}</div>;
}
