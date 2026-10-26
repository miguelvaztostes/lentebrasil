"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "./LoadingState";
import { fetchJson, type AgricultureResponse } from "@/lib/api";

export function AgricultureDashboard({ code }: { code: string }) {
  const [data, setData] = useState<AgricultureResponse | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchJson<AgricultureResponse>(`/sectors/agriculture?municipality=${encodeURIComponent(code)}&limit=200`).then(setData).catch((reason: Error) => setError(reason.message));
  }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  const available = data.items.filter((item) => item.value !== null);
  return <div><p className="eyebrow">Agropecuária e rural</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Quantidade produzida — PAM 2024</h1><p className="mt-5 max-w-3xl text-ink/65">PAM/IBGE por produto e ano. Valores ausentes ou protegidos permanecem indisponíveis: a ausência continua indisponível e não é convertida em zero.</p><section className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{available.length ? available.slice(0, 18).map((item) => <article className="card interactive-card border-t-4 border-t-[#657b3d] p-6" key={`${item.year}-${item.product.code}`}><p className="eyebrow">{item.year}</p><h2 className="mt-2 text-lg font-extrabold">{item.product.name}</h2><p className="mt-4 text-3xl font-black text-[#073f35]">{Number(item.value).toLocaleString("pt-BR")}</p><p className="mt-1 text-xs text-ink/55">{item.unit}</p></article>) : <article className="card p-8 md:col-span-2"><h2 className="text-xl font-extrabold">Sem produção publicada no recorte carregado</h2><p className="mt-3 text-sm text-ink/65">Ausência de publicação não significa produção zero.</p></article>}</section><details className="card mt-8 p-6"><summary className="cursor-pointer font-extrabold">Metodologia e proveniência</summary><p className="mt-4 text-sm leading-6 text-ink/65">{data.methodology}</p>{available[0] ? <div className="mt-4 text-sm"><p><strong>Período:</strong> {available[0].year}</p><p><strong>Dataset:</strong> {available[0].source.dataset}</p><p><strong>Licença/status:</strong> {available[0].source.license ?? "Atribuição ao IBGE"} · {available[0].source.publication_status}</p><a className="font-bold text-teal underline" href={available[0].source.url} target="_blank" rel="noreferrer">Abrir resposta oficial versionada</a></div> : null}</details></div>;
}
