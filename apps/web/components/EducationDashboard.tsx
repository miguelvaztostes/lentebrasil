"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "./LoadingState";
import {
  fetchJson,
  formatDate,
  type EducationMetric,
  type EducationMunicipality,
  type EducationSource,
} from "@/lib/api";

const metricLabels: Record<string, string> = {
  ideb: "Ideb",
  approval_rate: "Indicador de rendimento",
  saeb_mathematics: "Matemática",
  saeb_portuguese: "Língua Portuguesa",
  saeb_mean: "Média padronizada Saeb",
  pnae_students_planned: "Alunos considerados",
  pnae_transfer_planned_brl: "Valor previsto",
};

const stageLabels: Record<string, string> = {
  fundamental_early: "anos iniciais",
  fundamental_year_5: "5º ano",
  fundamental_year_9: "9º ano",
  secondary_year_3: "3ª/4ª série do ensino médio",
  pnae_daycare: "Creche",
  pnae_pre_school: "Pré-escola",
  pnae_fundamental: "Ensino fundamental",
  pnae_secondary: "Ensino médio",
  pnae_special_education: "AEE",
  pnae_youth_adult: "EJA",
  pnae_indigenous: "Educação indígena",
  pnae_quilombola: "Educação quilombola",
  pnae_full_time_secondary: "Ensino médio integral",
};

function SourceNote({ source }: { source: EducationSource | null | undefined }) {
  if (!source) {
    return (
      <p className="mt-3 text-xs text-ink/55">
        Ainda não há release homologado para este conjunto.
      </p>
    );
  }
  return (
    <p className="mt-3 text-xs leading-5 text-ink/55">
      Referência: {source.reference_end?.slice(0, 4) ?? "não informada"} · publicação no
      Lente: {formatDate(source.published_at)} ·{" "}
      <a
        className="font-bold text-teal underline"
        href={source.url ?? "#"}
        target="_blank"
        rel="noreferrer"
      >
        fonte oficial
      </a>
    </p>
  );
}

function MetricValue({ metric }: { metric: EducationMetric }) {
  if (metric.value == null) return <>—</>;
  const value = Number(metric.value);
  if (metric.indicator === "pnae_transfer_planned_brl") {
    return <>{value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</>;
  }
  return <>{value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}</>;
}

export function EducationDashboard({ code }: { code: string }) {
  const [data, setData] = useState<EducationMunicipality | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchJson<EducationMunicipality>(
      `/education/municipalities/${encodeURIComponent(code)}`,
    )
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  const ideb = data.metrics.filter(
    (metric) => !metric.dataset || metric.dataset === "inep_ideb_municipal",
  );
  const saebAll = data.metrics.filter((metric) => metric.dataset === "inep_saeb_municipal");
  const saebMunicipal = saebAll.filter((metric) => metric.network === "municipal");
  const saeb = saebMunicipal.length
    ? saebMunicipal
    : saebAll.filter((metric) => metric.network === "all");
  const pnae = data.metrics.filter((metric) => metric.dataset === "fnde_pnae_municipal");
  const pnaeStages = [...new Set(pnae.map((metric) => metric.stage))];

  return (
    <div>
      <p className="eyebrow">
        {data.municipality.name}/{data.municipality.state}
      </p>
      <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Educação</h1>
      <p className="mt-5 max-w-3xl text-ink/65">
        Escolas, matrículas, desempenho agregado e previsão de financiamento. Valores
        suprimidos ou ausentes na fonte permanecem indisponíveis, nunca são convertidos em zero.
      </p>

      <div className="mt-10 grid gap-5 md:grid-cols-2">
        <section className="card p-7">
          <p className="eyebrow">Censo Escolar</p>
          <p className="mt-3 text-4xl font-black">
            {data.sources.schools ? data.school_count.toLocaleString("pt-BR") : "Indisponível"}
          </p>
          <p className="mt-1 text-sm text-ink/65">escolas no recorte publicado</p>
          <p className="mt-5 text-3xl font-black">
            {data.enrollment_total == null
              ? "Indisponível"
              : data.enrollment_total.toLocaleString("pt-BR")}
          </p>
          <p className="mt-1 text-sm text-ink/65">matrículas na educação básica</p>
          <SourceNote source={data.sources.schools} />
        </section>

        <section className="card p-7">
          <p className="eyebrow">Ideb 2025 · anos iniciais</p>
          {ideb.length ? (
            <div className="mt-4 grid grid-cols-2 gap-4">
              {ideb.map((metric) => (
                <div key={`${metric.indicator}-${metric.network}`}>
                  <p className="text-xs text-ink/55">
                    {metricLabels[metric.indicator] ?? metric.indicator} · {metric.network}
                  </p>
                  <p className="text-2xl font-black"><MetricValue metric={metric} /></p>
                  <p className="text-[11px] text-ink/45">
                    {metric.availability_status === "suppressed"
                      ? "suprimido/indisponível na fonte"
                      : `ano ${metric.year}`}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-5 text-sm text-ink/65">Sem métricas publicadas para este município.</p>
          )}
          <SourceNote source={data.sources.ideb ?? data.sources.metrics} />
        </section>

        <section className="card p-7 md:col-span-2">
          <p className="eyebrow">Saeb 2023 · resultados municipais agregados</p>
          {saeb.length ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {saeb.map((metric) => (
                <div key={`${metric.indicator}-${metric.network}-${metric.stage}`}>
                  <p className="text-xs text-ink/55">
                    {metricLabels[metric.indicator] ?? metric.indicator} ·{" "}
                    {stageLabels[metric.stage] ?? metric.stage} · rede {metric.network}
                  </p>
                  <p className="text-2xl font-black"><MetricValue metric={metric} /></p>
                  <p className="text-[11px] text-ink/45">
                    {metric.availability_status === "suppressed"
                      ? "suprimido/indisponível na fonte"
                      : `média de proficiência · ${metric.year}`}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-5 text-sm text-ink/65">Sem release municipal homologado do Saeb.</p>
          )}
          <SourceNote source={data.sources.saeb} />
        </section>

        <section className="card p-7 md:col-span-2">
          <p className="eyebrow">PNAE 2024 · previsão por modalidade</p>
          {pnaeStages.length ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {pnaeStages.map((stage) => {
                const metrics = pnae.filter((metric) => metric.stage === stage);
                return (
                  <div key={stage} className="rounded-2xl border border-ink/10 p-4">
                    <p className="text-sm font-extrabold">{stageLabels[stage] ?? stage}</p>
                    {metrics.map((metric) => (
                      <div className="mt-3" key={metric.indicator}>
                        <p className="text-xs text-ink/55">
                          {metricLabels[metric.indicator] ?? metric.indicator}
                        </p>
                        <p className="text-xl font-black"><MetricValue metric={metric} /></p>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-5 text-sm text-ink/65">Sem previsão municipal homologada do PNAE.</p>
          )}
          <p className="mt-5 text-xs leading-5 text-ink/55">
            O valor é a previsão publicada pelo FNDE. Não representa pagamento realizado nem
            despesa executada pelo município. Os alunos de modalidades como AEE podem se sobrepor
            a outras etapas; por isso a plataforma não soma as categorias em um total de pessoas.
          </p>
          <SourceNote source={data.sources.fnde_pnae} />
        </section>
      </div>

      <div className="card mt-8 p-7">
        <h2 className="text-xl font-extrabold">Metodologia e limites</h2>
        <p className="mt-3 text-sm leading-6 text-ink/65">
          O Censo Escolar preserva somente atributos públicos e totais agregados. O Ideb e o Saeb
          respeitam recortes e supressões do Inep. O PNAE é reconciliado ao município pelo nome da
          prefeitura e UF no arquivo oficial. Nenhum dado individual de estudante ou profissional
          é armazenado ou exibido.
        </p>
      </div>
      <div className="mt-8 flex flex-wrap gap-4">
        <Link href="/buscar?sector=educacao" className="button-primary">Ver fontes de educação</Link>
        <Link href={`/municipios/${code}`} className="button-secondary">Voltar ao município</Link>
      </div>
    </div>
  );
}
