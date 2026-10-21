"use client";

import { useEffect, useState } from "react";
import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { fetchJson } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

type Detail = { kind: string; id: string; title: string; description?: string | null; area_label?: string; status?: string; source_status: string; connector_status: string; publication_status?: string; provider?: { name: string }; resource?: null | { url: string | null; format: string; license_status: string; license: string | null; last_verified_at: string | null }; raw?: Record<string, unknown>; url?: string; license?: string | null; verified_at?: string | null };

export function SourceDetail({ id }: { id: string }) {
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchJson<Detail>(`/sources/${encodeURIComponent(id)}`).then(setData).catch((reason: Error) => setError(reason.message)); }, [id]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Carregando proveniência da fonte…" />;
  const sourceUrl = data.resource?.url ?? data.url;
  return <div><p className="eyebrow">{data.kind === "catalog_candidate" ? `${data.id} · catálogo candidato` : "fonte integrada"}</p><div className="mt-3 flex flex-wrap items-start justify-between gap-5"><h1 className="max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">{data.title}</h1><StatusBadge status={data.status ?? data.source_status} /></div>{data.description && <p className="mt-6 max-w-3xl text-lg leading-8 text-ink/65">{data.description}</p>}<div className="mt-10 grid gap-5 md:grid-cols-2"><section className="card p-7"><h2 className="text-xl font-extrabold">Estado de publicação</h2><dl className="mt-5 grid gap-4 text-sm"><div><dt className="font-bold text-ink/50">Descoberta da fonte</dt><dd>{data.source_status}</dd></div><div><dt className="font-bold text-ink/50">Conector</dt><dd>{data.connector_status}</dd></div><div><dt className="font-bold text-ink/50">Dados</dt><dd>{data.publication_status ?? "não informado"}</dd></div></dl></section><section className="card p-7"><h2 className="text-xl font-extrabold">Uso e origem</h2><dl className="mt-5 grid gap-4 text-sm"><div><dt className="font-bold text-ink/50">Licença</dt><dd>{data.resource?.license ?? data.license ?? "pendente de confirmação"}</dd></div><div><dt className="font-bold text-ink/50">Estado da licença</dt><dd>{data.resource?.license_status ?? "não informado"}</dd></div></dl>{sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer" className="mt-6 inline-flex items-center gap-1 font-bold text-teal hover:underline">Abrir endereço indicado <ArrowTopRightOnSquareIcon className="h-4 w-4" /></a>}</section></div>{data.kind === "catalog_candidate" && <p className="mt-8 rounded-xl bg-gold/15 p-5 text-sm leading-6"><strong>Atenção:</strong> estar neste catálogo significa que a fonte foi descoberta no inventário. Não significa que o endpoint, a licença, a cobertura ou os dados tenham sido homologados.</p>}</div>;
}
