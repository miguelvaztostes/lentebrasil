"use client";

import { useEffect, useState } from "react";
import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { fetchJson, formatDate } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

type Source = { provider: string; slug: string; source_url: string; license: string | null; terms: string | null; expected_frequency: string | null; status: string; verified_at: string | null; failure_reason: string | null };
type Response = { items: Source[]; count: number };

export function SourcesList() {
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchJson<Response>("/sources?limit=100").then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  return <div className="grid gap-5 md:grid-cols-2">{data.items.map((source) => (
    <article key={source.slug} className="card p-6">
      <div className="flex items-start justify-between gap-4"><h2 className="text-xl font-extrabold">{source.provider}</h2><StatusBadge status={source.status} /></div>
      <dl className="mt-6 grid gap-4 text-sm">
        <div><dt className="font-bold text-ink/50">Frequência esperada</dt><dd className="mt-1">{source.expected_frequency ?? "não informada"}</dd></div>
        <div><dt className="font-bold text-ink/50">Licença</dt><dd className="mt-1">{source.license ?? "pendente de confirmação"}</dd></div>
        <div><dt className="font-bold text-ink/50">Verificada em</dt><dd className="mt-1">{formatDate(source.verified_at)}</dd></div>
      </dl>
      {source.failure_reason && <p className="mt-5 rounded-lg bg-gold/15 p-3 text-sm leading-6"><strong>Limitação:</strong> {source.failure_reason}</p>}
      {source.terms && <p className="mt-5 text-xs leading-5 text-ink/55">{source.terms}</p>}
      <a href={source.source_url} target="_blank" rel="noreferrer" className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-teal hover:underline">Abrir fonte oficial <ArrowTopRightOnSquareIcon className="h-4 w-4" /></a>
    </article>
  ))}</div>;
}

