"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchJson, type Municipality } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";

type Response = { items: Municipality[]; count: number; limit: number; offset: number };

export function StateDirectory({ uf }: { uf: string }) {
  const [page, setPage] = useState(0);
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState("");
  const limit = 60;
  useEffect(() => {
    setData(null);
    fetchJson<Response>(`/geo/municipios?uf=${encodeURIComponent(uf)}&limit=${limit}&offset=${page * limit}`).then(setData).catch((reason: Error) => setError(reason.message));
  }, [uf, page]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Carregando diretório estadual…" />;
  return <div><p className="mb-5 text-sm text-ink/55">{data.count} município(s) no diretório IBGE</p><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{data.items.map((item) => <Link key={item.ibge_code} href={`/municipios/${item.ibge_code}`} className="card p-5 transition hover:border-teal"><strong>{item.name}</strong><span className="mt-1 block text-xs text-ink/50">{item.ibge_code}</span></Link>)}</div><div className="mt-8 flex items-center justify-between"><button disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="button-secondary disabled:opacity-40">Anterior</button><span className="text-sm">Página {page + 1}</span><button disabled={(page + 1) * limit >= data.count} onClick={() => setPage((value) => value + 1)} className="button-secondary disabled:opacity-40">Próxima</button></div></div>;
}
