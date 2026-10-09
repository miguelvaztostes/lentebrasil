"use client";

import { useEffect, useState } from "react";
import { fetchJson, formatDate } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

type Pipeline = { dataset: string; title: string; catalog_status: string; last_run: null | { started_at: string; finished_at: string | null; status: string; items_received: number; items_accepted: number; items_rejected: number } };
type Response = { items: Pipeline[] };

export function PipelinesStatus() {
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchJson<Response>("/pipelines/status").then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  return <div className="overflow-x-auto card p-5"><table className="w-full min-w-[700px] text-left text-sm"><caption className="sr-only">Estado das integrações</caption><thead><tr className="border-b-2 border-ink"><th className="py-3">Dataset</th><th>Estado</th><th>Última execução</th><th>Aceitos</th><th>Rejeitados</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.dataset} className="border-b border-ink/10"><td className="py-4 font-bold">{item.title}</td><td><StatusBadge status={item.last_run?.status ?? item.catalog_status} /></td><td>{item.last_run ? formatDate(item.last_run.finished_at ?? item.last_run.started_at) : "ainda não executado"}</td><td>{item.last_run?.items_accepted ?? "—"}</td><td>{item.last_run?.items_rejected ?? "—"}</td></tr>)}</tbody></table></div>;
}

