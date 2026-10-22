"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "./LoadingState";
import { fetchJson, formatDate, type EducationMunicipality, type EducationSource } from "@/lib/api";

const labels: Record<string, string> = {
  ideb: "Ideb",
  approval_rate: "Indicador de rendimento",
  saeb_mathematics: "Saeb · Matemática",
  saeb_portuguese: "Saeb · Língua Portuguesa",
  saeb_mean: "Média padronizada Saeb",
};

function SourceNote({ source }: { source: EducationSource | null }) {
  if (!source) return <p className="mt-3 text-xs text-ink/55">Ainda não há release homologado para este conjunto.</p>;
  return <p className="mt-3 text-xs leading-5 text-ink/55">Referência: {source.reference_end?.slice(0, 4) ?? "não informada"} · publicação no Lente: {formatDate(source.published_at)} · <a className="font-bold text-teal underline" href={source.url ?? "#"} target="_blank" rel="noreferrer">fonte oficial</a></p>;
}

export function EducationDashboard({ code }: { code: string }) {
  const [data, setData] = useState<EducationMunicipality | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchJson<EducationMunicipality>(`/education/municipalities/${encodeURIComponent(code)}`).then(setData).catch((reason: Error) => setError(reason.message)); }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  return <div>
    <p className="eyebrow">{data.municipality.name}/{data.municipality.state}</p>
    <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Educação</h1>
    <p className="mt-5 max-w-3xl text-ink/65">Escolas e matrículas do Censo Escolar e indicadores municipais do Ideb. Valores suprimidos pelo Inep permanecem indisponíveis — nunca são convertidos em zero.</p>
    <div className="mt-10 grid gap-5 md:grid-cols-2">
      <section className="card p-7"><p className="eyebrow">Censo Escolar</p><p className="mt-3 text-4xl font-black">{data.sources.schools ? data.school_count.toLocaleString("pt-BR") : "Indisponível"}</p><p className="mt-1 text-sm text-ink/65">escolas no recorte publicado</p><p className="mt-5 text-3xl font-black">{data.enrollment_total == null ? "Indisponível" : data.enrollment_total.toLocaleString("pt-BR")}</p><p className="mt-1 text-sm text-ink/65">matrículas na educação básica</p><SourceNote source={data.sources.schools} /></section>
      <section className="card p-7"><p className="eyebrow">Ideb 2025 · anos iniciais</p>{data.metrics.length ? <div className="mt-4 grid grid-cols-2 gap-4">{data.metrics.map((metric) => <div key={`${metric.indicator}-${metric.network}`}><p className="text-xs text-ink/55">{labels[metric.indicator] ?? metric.indicator} · {metric.network}</p><p className="text-2xl font-black">{metric.value == null ? "—" : Number(metric.value).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}</p><p className="text-[11px] text-ink/45">{metric.availability_status === "suppressed" ? "suprimido/indisponível na fonte" : `ano ${metric.year}`}</p></div>)}</div> : <p className="mt-5 text-sm text-ink/65">Sem métricas publicadas para este município.</p>}<SourceNote source={data.sources.metrics} /></section>
    </div>
    <div className="card mt-8 p-7"><h2 className="text-xl font-extrabold">Metodologia e limites</h2><p className="mt-3 text-sm leading-6 text-ink/65">O Censo Escolar preserva apenas atributos públicos da escola e totais agregados; endereço, telefone, CNPJ e qualquer registro individual não são armazenados. O Ideb é mostrado por rede e etapa conforme o pacote oficial, inclusive suas regras de supressão.</p></div>
    <div className="mt-8 flex flex-wrap gap-4"><Link href={`/buscar?sector=educacao`} className="button-primary">Ver fontes de educação</Link><Link href={`/municipios/${code}`} className="button-secondary">Voltar ao município</Link></div>
  </div>;
}
