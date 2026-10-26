"use client";

import {
  AcademicCapIcon,
  ArrowRightIcon,
  BuildingLibraryIcon,
  ChartBarIcon,
  InformationCircleIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorState, LoadingState } from "./LoadingState";
import {
  fetchJson,
  formatDate,
  type EducationBreakdown,
  type EducationMetric,
  type EducationMunicipality,
  type EducationSource,
} from "@/lib/api";

const metricLabels: Record<string, string> = {
  ideb: "Ideb",
  approval_rate: "Rendimento escolar",
  saeb_mathematics: "Matemática",
  saeb_portuguese: "Língua Portuguesa",
  saeb_mean: "Média padronizada Saeb",
  pnae_students_planned: "Alunos considerados",
  pnae_transfer_planned_brl: "Valor previsto",
};

const stageLabels: Record<string, string> = {
  fundamental_early: "Anos iniciais",
  fundamental_year_5: "5º ano",
  fundamental_year_9: "9º ano",
  secondary_year_3: "3ª/4ª série do ensino médio",
  pnae_daycare: "Creche",
  pnae_pre_school: "Pré-escola",
  pnae_fundamental: "Ensino fundamental",
  pnae_secondary: "Ensino médio",
  pnae_special_education: "Atendimento educacional especializado",
  pnae_youth_adult: "Educação de jovens e adultos",
  pnae_indigenous: "Educação indígena",
  pnae_quilombola: "Educação quilombola",
  pnae_full_time_secondary: "Ensino médio integral",
};

const networkLabels: Record<string, string> = {
  all: "Todas as redes",
  public: "Rede pública",
  federal: "Rede federal",
  state: "Rede estadual",
  municipal: "Rede municipal",
  private: "Rede privada",
};

function SourceNote({ source }: { source: EducationSource | null | undefined }) {
  if (!source) return <p className="mt-4 text-xs text-ink/50">Ainda não há release homologado para este conjunto.</p>;
  return (
    <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-ink/10 pt-4 text-xs leading-5 text-ink/55">
      <span>Referência {source.reference_end?.slice(0, 4) ?? "não informada"}</span>
      <span aria-hidden="true">·</span>
      <span>Publicado no Lente em {formatDate(source.published_at)}</span>
      {source.url && (
        <a className="font-bold text-[#087875] underline decoration-teal/30 underline-offset-4 hover:decoration-teal" href={source.url} target="_blank" rel="noreferrer">
          Abrir fonte oficial
        </a>
      )}
    </div>
  );
}

function MetricValue({ metric, className = "" }: { metric: EducationMetric; className?: string }) {
  if (metric.value == null) return <span className={className}>Indisponível</span>;
  const value = Number(metric.value);
  let formatted = value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  if (metric.indicator === "pnae_transfer_planned_brl") formatted = value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  if (metric.indicator === "approval_rate") formatted = `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  return <span className={className}>{formatted}</span>;
}

function BreakdownBars({ items, color = "bg-teal" }: { items: EducationBreakdown[]; color?: string }) {
  const maximum = Math.max(...items.map((item) => Number(item.value)), 1);
  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.code}>
          <div className="mb-1.5 flex items-baseline justify-between gap-4 text-sm">
            <span className="font-semibold">{item.label}</span>
            <span className="font-black tabular-nums">{Number(item.value).toLocaleString("pt-BR")}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-ink/8">
            <div className={`reveal-bar h-full origin-left rounded-full ${color}`} style={{ width: `${Math.max((Number(item.value) / maximum) * 100, 2)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function EducationDashboard({ code }: { code: string }) {
  const [data, setData] = useState<EducationMunicipality | null>(null);
  const [error, setError] = useState("");
  const [selectedSaebNetwork, setSelectedSaebNetwork] = useState("municipal");

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    fetchJson<EducationMunicipality>(`/education/municipalities/${encodeURIComponent(code)}`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [code]);

  const analysis = useMemo(() => {
    const metrics = data?.metrics ?? [];
    const ideb = metrics.filter((metric) => !metric.dataset || metric.dataset === "inep_ideb_municipal");
    const saebAll = metrics.filter((metric) => metric.dataset === "inep_saeb_municipal");
    const pnae = metrics.filter((metric) => metric.dataset === "fnde_pnae_municipal");
    const saebNetworks = [...new Set(saebAll.map((metric) => metric.network))];
    const network = saebNetworks.includes(selectedSaebNetwork) ? selectedSaebNetwork : (saebNetworks[0] ?? "all");
    const saeb = saebAll.filter((metric) => metric.network === network);
    const idebNetworks = [...new Set(ideb.map((metric) => metric.network))];
    const saebStages = [...new Set(saeb.map((metric) => metric.stage))];
    const pnaeStages = [...new Set(pnae.map((metric) => metric.stage))];
    const pnaeTransferTotal = pnae
      .filter((metric) => metric.indicator === "pnae_transfer_planned_brl" && metric.value != null)
      .reduce((sum, metric) => sum + Number(metric.value), 0);
    return { ideb, saebAll, saeb, pnae, saebNetworks, network, idebNetworks, saebStages, pnaeStages, pnaeTransferTotal };
  }, [data, selectedSaebNetwork]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  const municipalIdeb = analysis.ideb.find((metric) => metric.network === "municipal" && metric.indicator === "ideb");
  const censusYear = data.sources.schools?.reference_end?.slice(0, 4) ?? "—";
  const idebYear = analysis.ideb[0]?.year ?? "—";
  const saebYear = analysis.saebAll[0]?.year ?? "—";
  const saebLabel = analysis.saebAll.length ? `Saeb ${saebYear}` : "Saeb 2023";

  return (
    <div>
      <section className="editorial-hero rounded-[2rem] px-6 py-9 shadow-[0_30px_80px_rgba(6,47,41,0.22)] sm:px-10 sm:py-12 lg:px-14">
        <div className="relative z-10 max-w-5xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f2ca61]">{data.municipality.name}/{data.municipality.state}</p>
          <h1 className="display-title mt-4 max-w-3xl text-5xl leading-[0.94] sm:text-7xl">Educação em perspectiva</h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-white/75">
            Estrutura da rede, matrículas, aprendizagem e financiamento reunidos sem esconder diferenças de ano ou metodologia.
          </p>
          <div className="mt-9 grid gap-3 sm:grid-cols-3">
            <div className="metric-tile rounded-2xl p-5 transition duration-300 hover:-translate-y-1 hover:bg-white/15">
              <BuildingLibraryIcon className="h-5 w-5 text-[#f2ca61]" />
              <p className="mt-3 text-3xl font-black">{data.sources.schools ? data.school_count.toLocaleString("pt-BR") : "—"}</p>
              <p className="mt-1 text-xs text-white/65">escolas · Censo {censusYear}</p>
            </div>
            <div className="metric-tile rounded-2xl p-5 transition duration-300 hover:-translate-y-1 hover:bg-white/15">
              <AcademicCapIcon className="h-5 w-5 text-[#f2ca61]" />
              <p className="mt-3 text-3xl font-black">{data.enrollment_total == null ? "—" : data.enrollment_total.toLocaleString("pt-BR")}</p>
              <p className="mt-1 text-xs text-white/65">matrículas na educação básica</p>
            </div>
            <div className="metric-tile rounded-2xl p-5 transition duration-300 hover:-translate-y-1 hover:bg-white/15">
              <ChartBarIcon className="h-5 w-5 text-[#f2ca61]" />
              <p className="mt-3 text-3xl font-black"><MetricValue metric={municipalIdeb ?? { year: 0, indicator: "ideb", network: "municipal", stage: "", value: null, availability_status: "unavailable" }} /></p>
              <p className="mt-1 text-xs text-white/65">Ideb municipal · {idebYear}</p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-white/70">
            {[`Censo ${censusYear}`, `Ideb ${idebYear}`, saebLabel, "PNAE 2024"].map((label) => <span key={label} className="rounded-full border border-white/20 px-3 py-1.5">{label}</span>)}
          </div>
        </div>
      </section>

      <div className="mt-5 flex gap-3 rounded-2xl border border-gold/35 bg-gold/10 p-4 text-sm leading-6 text-ink/70">
        <InformationCircleIcon className="mt-0.5 h-5 w-5 shrink-0 text-[#9a6e11]" />
        <p>Os conjuntos têm anos de referência diferentes. Eles ajudam a compor o retrato educacional, mas não devem ser lidos como medições do mesmo período.</p>
      </div>

      <nav aria-label="Seções da página" className="mt-8 flex gap-2 overflow-x-auto pb-2">
        {["Rede e matrículas", "Ideb", "Saeb", "PNAE", "Metodologia"].map((label) => (
          <a key={label} href={`#${label.toLocaleLowerCase("pt-BR").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replaceAll(" ", "-")}`} className="whitespace-nowrap rounded-full border border-ink/15 bg-white px-4 py-2 text-sm font-bold transition hover:-translate-y-0.5 hover:border-teal hover:text-teal">{label}</a>
        ))}
      </nav>

      <section id="rede-e-matriculas" className="mt-14 scroll-mt-32" aria-labelledby="network-title">
        <p className="eyebrow">Censo Escolar {censusYear}</p>
        <h2 id="network-title" className="display-title mt-2 text-4xl sm:text-5xl">Como a rede está distribuída</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/60">Os totais abaixo vêm da mesma publicação do Censo. Matrículas por etapa são recortes educacionais e não devem ser somadas entre si sem observar sobreposições.</p>
        <div className="mt-7 grid gap-5 lg:grid-cols-2">
          <article className="card interactive-card p-6 sm:p-8">
            <h3 className="text-lg font-black">Matrículas por dependência administrativa</h3>
            <p className="mt-1 text-xs text-ink/50">Distribuição do total da educação básica</p>
            <div className="mt-7"><BreakdownBars items={data.enrollments_by_dependency} /></div>
          </article>
          <article className="card interactive-card p-6 sm:p-8">
            <h3 className="text-lg font-black">Escolas por dependência administrativa</h3>
            <p className="mt-1 text-xs text-ink/50">Quantidade de estabelecimentos no recorte publicado</p>
            <div className="mt-7"><BreakdownBars items={data.schools_by_dependency} color="bg-[#d7a329]" /></div>
          </article>
          <article className="card p-6 sm:p-8 lg:col-span-2">
            <h3 className="text-lg font-black">Matrículas por etapa e modalidade</h3>
            <div className="mt-6 grid gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
              {data.enrollments_by_stage.map((item) => (
                <div key={item.code} className="border-l-2 border-teal/35 pl-4 transition duration-300 hover:border-gold hover:pl-5">
                  <p className="text-xs leading-5 text-ink/50">{item.label}</p>
                  <p className="mt-1 text-2xl font-black tabular-nums">{Number(item.value).toLocaleString("pt-BR")}</p>
                </div>
              ))}
            </div>
            <SourceNote source={data.sources.schools} />
          </article>
        </div>
      </section>

      <section id="ideb" className="mt-20 scroll-mt-32" aria-labelledby="ideb-title">
        <p className="eyebrow">Ideb {idebYear} · anos iniciais</p>
        <h2 id="ideb-title" className="display-title mt-2 text-4xl sm:text-5xl">Aprendizagem e fluxo escolar</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/60">O Ideb combina rendimento escolar e desempenho no Saeb. Os cartões mantêm cada rede separada para evitar comparações indevidas.</p>
        {analysis.idebNetworks.length ? (
          <div className="mt-7 grid gap-5 lg:grid-cols-3">
            {analysis.idebNetworks.map((network) => {
              const metrics = analysis.ideb.filter((metric) => metric.network === network);
              const score = metrics.find((metric) => metric.indicator === "ideb");
              return (
                <article key={network} className="card interactive-card overflow-hidden">
                  <div className="bg-[#073f35] px-6 py-5 text-white">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-white/65">{networkLabels[network] ?? network}</p>
                    <p className="mt-3 text-5xl font-black"><MetricValue metric={score ?? metrics[0]} /></p>
                    <p className="mt-1 text-xs text-white/60">índice de 0 a 10</p>
                  </div>
                  <div className="grid grid-cols-2 gap-5 p-6">
                    {metrics.filter((metric) => metric.indicator !== "ideb").map((metric) => (
                      <div key={metric.indicator}>
                        <p className="text-[11px] leading-4 text-ink/50">{metricLabels[metric.indicator] ?? metric.indicator}</p>
                        <p className="mt-1 text-xl font-black"><MetricValue metric={metric} /></p>
                      </div>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        ) : <p className="card mt-7 p-7 text-sm text-ink/65">Sem métricas publicadas para este município.</p>}
        <SourceNote source={data.sources.ideb ?? data.sources.metrics} />
      </section>

      <section id="saeb" className="mt-20 scroll-mt-32" aria-labelledby="saeb-title">
        <p className="eyebrow">Saeb {saebYear}</p>
        <h2 id="saeb-title" className="display-title mt-2 text-4xl sm:text-5xl">Proficiência por etapa</h2>
        <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Selecionar rede do Saeb">
          {analysis.saebNetworks.map((network) => (
            <button key={network} type="button" onClick={() => setSelectedSaebNetwork(network)} className={`rounded-full px-4 py-2 text-sm font-bold transition duration-300 ${analysis.network === network ? "bg-[#073f35] text-white shadow-lg" : "border border-ink/15 bg-white hover:-translate-y-0.5 hover:border-teal hover:text-teal"}`}>
              {networkLabels[network] ?? network}
            </button>
          ))}
        </div>
        {analysis.saebStages.length ? (
          <div className="mt-7 grid gap-5 lg:grid-cols-3">
            {analysis.saebStages.map((stage) => (
              <article key={stage} className="card interactive-card p-6">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal">{stageLabels[stage] ?? stage}</p>
                <div className="mt-6 space-y-5">
                  {analysis.saeb.filter((metric) => metric.stage === stage).map((metric) => (
                    <div key={metric.indicator} className="flex items-end justify-between gap-4 border-b border-ink/8 pb-4 last:border-0 last:pb-0">
                      <p className="text-sm text-ink/60">{metricLabels[metric.indicator] ?? metric.indicator}</p>
                      <p className="text-2xl font-black"><MetricValue metric={metric} /></p>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : <p className="card mt-7 p-7 text-sm text-ink/65">Sem release municipal homologado do Saeb.</p>}
        <SourceNote source={data.sources.saeb} />
      </section>

      <section id="pnae" className="mt-20 scroll-mt-32" aria-labelledby="pnae-title">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow">PNAE 2024</p>
            <h2 id="pnae-title" className="display-title mt-2 text-4xl sm:text-5xl">Alimentação escolar planejada</h2>
          </div>
          {analysis.pnaeTransferTotal > 0 && (
            <div className="rounded-2xl bg-gold/15 px-5 py-4 text-right">
              <p className="text-xs text-ink/55">previsão somada nas modalidades exibidas</p>
              <p className="mt-1 text-2xl font-black">{analysis.pnaeTransferTotal.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</p>
            </div>
          )}
        </div>
        {analysis.pnaeStages.length ? (
          <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {analysis.pnaeStages.map((stage) => (
              <article key={stage} className="card interactive-card p-5">
                <p className="min-h-10 text-sm font-black leading-5">{stageLabels[stage] ?? stage}</p>
                {analysis.pnae.filter((metric) => metric.stage === stage).map((metric) => (
                  <div className="mt-4 border-t border-ink/8 pt-3" key={metric.indicator}>
                    <p className="text-xs text-ink/50">{metricLabels[metric.indicator] ?? metric.indicator}</p>
                    <p className="mt-1 text-xl font-black"><MetricValue metric={metric} /></p>
                  </div>
                ))}
              </article>
            ))}
          </div>
        ) : <p className="card mt-7 p-7 text-sm text-ink/65">Sem previsão municipal homologada do PNAE.</p>}
        <p className="mt-5 max-w-4xl text-xs leading-5 text-ink/55">O valor é a previsão publicada pelo FNDE. Não representa pagamento realizado nem despesa executada pelo município. Os alunos de modalidades como atendimento especializado podem se sobrepor a outras etapas; por isso a plataforma não soma as categorias em um total de pessoas.</p>
        <SourceNote source={data.sources.fnde_pnae} />
      </section>

      <section id="metodologia" className="mt-20 scroll-mt-32 rounded-[2rem] bg-[#073f35] p-7 text-white sm:p-10">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#f2ca61]">Leia os dados com contexto</p>
        <h2 className="display-title mt-3 text-4xl">Metodologia e limites</h2>
        <p className="mt-5 max-w-4xl text-sm leading-7 text-white/70">O Censo Escolar preserva somente atributos públicos e totais agregados. O Ideb e o Saeb respeitam recortes e supressões do Inep. O PNAE é reconciliado ao município pelo nome da prefeitura e UF no arquivo oficial. Valores suprimidos ou ausentes permanecem indisponíveis, nunca são convertidos em zero. Nenhum dado individual de estudante ou profissional é armazenado ou exibido.</p>
      </section>

      <div className="mt-9 flex flex-wrap gap-3">
        <Link href={`/comparar?indicador=education:ideb&municipios=${code},3509502,3550308`} className="button-primary gap-2">Comparar Ideb <ArrowRightIcon className="h-4 w-4" /></Link>
        <Link href={`/comparar?indicador=education:saeb_mathematics&municipios=${code},3509502,3550308`} className="button-secondary">Comparar Saeb</Link>
        <Link href={`/comparar?indicador=education:enrollment_count&municipios=${code},3509502,3550308`} className="button-secondary">Comparar matrículas</Link>
        <Link href="/buscar?sector=educacao" className="button-secondary">Ver fontes de educação</Link>
        <Link href={`/municipios/${code}`} className="button-secondary">Voltar ao município</Link>
      </div>
    </div>
  );
}
