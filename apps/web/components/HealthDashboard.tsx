"use client";

import { useEffect, useState } from "react";
import { API_BASE, fetchJson, type HealthOverview } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";

const formatCount = (value: number | null) =>
  value == null ? "Não disponível" : value.toLocaleString("pt-BR");

const formatCurrency = (value: string | null) =>
  value == null
    ? "Não disponível"
    : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(Number(value));

export function HealthDashboard({ code }: { code: string }) {
  const [year, setYear] = useState("2024");
  const [data, setData] = useState<HealthOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    fetchJson<HealthOverview>(
      `/health/overview?municipality=${encodeURIComponent(code)}&year=${year}`,
    )
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, [code, year]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  const causes = data.epidemiology.causes
    .filter((item) => item.count != null && item.count > 0)
    .sort((left, right) => (right.count ?? 0) - (left.count ?? 0))
    .slice(0, 8);
  const sia = data.production.items.outpatient_procedures_approved;
  const sih = data.production.items.hospital_admissions_authorizations;

  return (
    <div className="space-y-10">
      <header>
        <p className="eyebrow">{data.municipality.name}/{data.municipality.state}</p>
        <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Saúde</h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-ink/65">
          Rede cadastrada, capacidade, mortalidade e nascidos vivos em recortes separados.
          Cadastro, produção assistencial e eventos vitais não são tratados como equivalentes.
        </p>
        <label className="mt-6 block max-w-44 text-sm font-bold">
          Ano de referência
          <select className="mt-2 w-full rounded-lg border border-ink/20 p-3 font-normal" value={year} onChange={(event) => setYear(event.target.value)}>
            <option value="2024">2024</option>
          </select>
        </label>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Metric label="Estabelecimentos CNES" value={formatCount(data.network.establishments)} method={data.network.methodology} />
        <Metric label="Leitos cadastrados" value={formatCount(data.network.registered_beds)} method={data.network.methodology} />
        <Metric label={`Óbitos SIM ${year}`} value={formatCount(data.epidemiology.total_deaths)} method={data.epidemiology.methodology} />
        <Metric label={`Nascidos vivos SINASC ${year}`} value={formatCount(data.epidemiology.live_births)} method="Registros do SINASC agregados pelo município de residência." />
        <Metric label={`Procedimentos SIA ${data.production.reference_period ?? ""}`} value={formatCount(sia?.quantity == null ? null : Number(sia.quantity))} method="Procedimentos ambulatoriais aprovados; não representam pessoas únicas." />
        <Metric label={`Autorizações SIH ${data.production.reference_period ?? ""}`} value={formatCount(sih?.quantity == null ? null : Number(sih.quantity))} method="Autorizações de internação; não representam pessoas únicas." />
        <Metric label={`Despesa paga SIOPS ${data.health_spending.reference_year ?? ""}`} value={formatCurrency(data.health_spending.value)} method={data.health_spending.methodology} />
        <Metric label={`Vínculos de beneficiários ANS ${data.supplementary_health.reference_period ?? ""}`} value={formatCount(data.supplementary_health.beneficiary_links == null ? null : Number(data.supplementary_health.beneficiary_links))} method={data.supplementary_health.methodology} />
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><p className="eyebrow">SIM · residência</p><h2 className="mt-2 text-3xl font-black">Mortalidade por capítulo CID-10</h2></div>
          <a className="button-secondary" href={`${API_BASE}/v1/health/exports/epidemiology.csv?municipality=${encodeURIComponent(code)}&year=${year}`}>Exportar CSV</a>
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">{data.epidemiology.methodology} Contagens entre 1 e 4 são suprimidas; ausência de dado nunca é exibida como zero.</p>
        {causes.length === 0 ? <Empty /> : <div className="mt-5 grid gap-4 md:grid-cols-2">{causes.map((item) => <article className="card p-5" key={item.code}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wider text-ink/50">Capítulo CID-10</p><h3 className="mt-2 font-extrabold">{item.name}</h3></div><p className="text-2xl font-black">{formatCount(item.count)}</p></div></article>)}</div>}
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <article className="card p-6"><p className="eyebrow">Produção assistencial · {data.production.reference_period ?? "sem carga"}</p><h2 className="mt-2 text-2xl font-black">SIA/SUS e SIH/SUS</h2>{data.production.availability === "available" ? <div className="mt-5 grid grid-cols-2 gap-4"><div><p className="text-xs text-ink/55">Procedimentos ambulatoriais aprovados</p><p className="mt-1 text-2xl font-black">{formatCount(sia?.quantity == null ? null : Number(sia.quantity))}</p><p className="mt-1 text-xs text-ink/50">{formatCurrency(sia?.approved_amount ?? null)}</p></div><div><p className="text-xs text-ink/55">Autorizações de internação</p><p className="mt-1 text-2xl font-black">{formatCount(sih?.quantity == null ? null : Number(sih.quantity))}</p><p className="mt-1 text-xs text-ink/50">{formatCurrency(sih?.approved_amount ?? null)}</p></div></div> : <p className="mt-4 font-bold">Não disponível</p>}<p className="mt-4 text-sm leading-6 text-ink/65">{data.production.methodology}</p>{data.production.availability === "available" && <a className="mt-4 inline-block text-sm font-bold text-teal underline" href={`${API_BASE}/v1/health/production?municipality=${encodeURIComponent(code)}&year=2025`} target="_blank" rel="noreferrer">Consultar procedimentos na API</a>}</article>
        <article className="card p-6"><p className="eyebrow">Financiamento</p><h2 className="mt-2 text-2xl font-black">Gastos municipais em saúde</h2><p className="mt-3 text-3xl font-black">{formatCurrency(data.health_spending.value)}</p><p className="mt-4 text-sm leading-6 text-ink/65">{data.health_spending.methodology}</p>{data.health_spending.availability === "available" && <a className="mt-4 inline-block text-sm font-bold text-teal underline" href={`${API_BASE}/v1/health/spending?municipality=${encodeURIComponent(code)}&year=2025&phase=paid&top_level_only=true`} target="_blank" rel="noreferrer">Consultar fases e rubricas na API</a>}</article>
      </section>

      <details className="card p-6">
        <summary className="cursor-pointer font-extrabold">Cobertura, proveniência e limites</summary>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">{data.sources.map((source) => <div key={source.dataset}><p className="font-bold">{source.dataset}</p><p className="mt-1 text-sm text-ink/60">{source.provider ?? "Fonte ainda não configurada"} · conector {source.connector_status ?? "não configurado"} · publicação {source.publication_status ?? "não informada"}</p>{source.url && <a className="mt-2 inline-block text-sm font-bold text-teal underline" href={source.url} target="_blank" rel="noreferrer">Fonte oficial</a>}</div>)}</div>
        <p className="mt-5 text-sm leading-6 text-ink/65">CNES descreve cadastro, não disponibilidade em tempo real. SIM registra óbitos; SINASC registra nascidos vivos por residência. Nenhum deles mede casos notificados ou confirmados. Não há prontuários, nomes, endereços de pacientes ou cruzamento entre causa e idade nesta publicação.</p>
      </details>
    </div>
  );
}

function Metric({ label, value, method }: { label: string; value: string; method: string }) {
  return <article className="card interactive-card border-t-4 border-t-teal p-5"><p className="text-xs font-bold uppercase tracking-wider text-ink/50">{label}</p><p className="mt-3 text-2xl font-black text-[#073f35]">{value}</p><p className="mt-3 text-xs leading-5 text-ink/55">{method}</p></article>;
}

function Empty() {
  return <div className="card mt-5 p-6"><p className="font-bold">Nenhum dado publicado para este recorte.</p><p className="mt-2 text-sm text-ink/65">A ausência não é convertida em zero.</p></div>;
}
