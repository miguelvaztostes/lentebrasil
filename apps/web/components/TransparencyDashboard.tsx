"use client";

import { useEffect, useState } from "react";
import { API_BASE, fetchJson, type FiscalStatement, type Paged, type Procurement, type TransparencyOverview } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";
import { DomainDashboard } from "./DomainDashboard";

const money = (value: string | null) => value === null ? "Não informado" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
const fiscalCodes = ["revenue_realized", "expense_committed", "expense_liquidated", "expense_paid"];
const phaseNames: Record<string, string> = { committed: "Empenhado", liquidated: "Liquidado", paid: "Pago", reinforcement: "Reforços", annulment: "Anulações" };
const months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

export function TransparencyDashboard({ municipalityCode = "3543402" }: { municipalityCode?: string }) {
  const [year, setYear] = useState("");
  const [month, setMonth] = useState("");
  const [query, setQuery] = useState("");
  const [fiscal, setFiscal] = useState<Paged<FiscalStatement> | null>(null);
  const [procurements, setProcurements] = useState<Paged<Procurement> | null>(null);
  const [overview, setOverview] = useState<TransparencyOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    const suffix = `municipality=${encodeURIComponent(municipalityCode)}${year ? `&year=${year}` : ""}`;
    const fiscalSuffix = `${suffix}${month ? `&period=${month}` : ""}`;
    Promise.all([
      fetchJson<TransparencyOverview>(`/transparency/overview?${fiscalSuffix}`),
      fetchJson<Paged<FiscalStatement>>(`/transparency/fiscal-statements?${fiscalSuffix}&limit=12`),
      fetchJson<Paged<Procurement>>(`/transparency/procurements?${suffix}&limit=12`),
    ]).then(([overviewData, fiscalData, procurementData]) => { setOverview(overviewData); setFiscal(fiscalData); setProcurements(procurementData); }).catch((reason: Error) => setError(reason.message));
  }, [municipalityCode, year, month]);

  if (error) return <ErrorState message={error} />;
  if (!overview || !fiscal || !procurements) return <LoadingState />;
  const visible = procurements.items.filter((item) => !query || `${item.object} ${item.agency}`.toLocaleLowerCase("pt-BR").includes(query.toLocaleLowerCase("pt-BR")));
  const csvQuery = `municipality=${encodeURIComponent(municipalityCode)}${year ? `&year=${year}` : ""}`;
  const fiscalCsvQuery = `${csvQuery}${month ? `&period=${month}` : ""}`;
  const phaseAmount = (phase: string) => overview.expense_phases.find((item) => item.phase === phase)?.amount ?? null;

  return <div className="space-y-10">
    <section>
      <p className="eyebrow">Visão geral da transparência</p>
      <h2 className="mt-2 text-3xl font-black">Receitas, fases da despesa e contratações</h2>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <OverviewCard label="Receita arrecadada" value={money(overview.revenue_collected)} available={overview.availability.revenue === "available"} />
        {(["committed", "liquidated", "paid"] as const).map((phase) => <OverviewCard key={phase} label={phaseNames[phase]} value={money(phaseAmount(phase))} available={phaseAmount(phase) !== null} />)}
        <OverviewCard label="Contratações PNCP" value={overview.availability.procurements === "available" ? String(overview.procurements) : "Não disponível"} available={overview.availability.procurements === "available"} />
        <OverviewCard label="Contratos PNCP" value={overview.availability.contracts === "available" ? String(overview.contracts) : "Não disponível"} available={overview.availability.contracts === "available"} />
      </div>
      {overview.expense_phases.some((item) => ["reinforcement", "annulment"].includes(item.phase)) && <p className="mt-4 text-sm text-ink/65">{overview.expense_phases.filter((item) => ["reinforcement", "annulment"].includes(item.phase)).map((item) => `${phaseNames[item.phase]}: ${money(item.amount)}`).join(" · ")}. Esses eventos não são compensados automaticamente.</p>}
      <p className="mt-4 max-w-4xl text-sm leading-6 text-ink/65">{overview.methodology}</p>
      <details className="card mt-5 p-5"><summary className="cursor-pointer font-extrabold">Cobertura e limites desta visão</summary><div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">{overview.sources.map((source) => <p key={source.dataset}><a className="font-bold underline" href={source.url} target="_blank" rel="noreferrer">{source.dataset}</a><br /><span className="text-ink/60">{source.provider} · conector {source.connector_status ?? "não configurado"} · licença/status {source.license ?? "não declarado"}</span></p>)}</div><p className="mt-4 text-sm leading-6 text-ink/65">Atas e PCA do PNCP são recursos complementares já verificados, mas ainda não compõem os totais desta página. CGU depende de token autorizado; o portal municipal permanece fora enquanto não houver exportação estruturada e reutilizável.</p></details>
    </section>
    <section>
      <p className="eyebrow">Séries RREO</p>
      <h2 className="mt-2 text-3xl font-black">Receitas e fases da despesa</h2>
      <p className="mb-5 mt-3 max-w-3xl text-sm leading-6 text-ink/65">Gráficos do RREO mantêm receita realizada, empenho, liquidação e pagamento em séries independentes. Períodos acumulados não são tratados como meses isolados.</p>
      <DomainDashboard municipalityCode={municipalityCode} codes={fiscalCodes} />
    </section>
    <section className="card p-6">
      <div className="grid gap-4 sm:grid-cols-4">
        <label className="text-sm font-bold">Exercício<input className="mt-2 w-full rounded-lg border border-ink/20 p-3 font-normal" inputMode="numeric" placeholder={`Último disponível (${overview.year})`} value={year} onChange={(event) => setYear(event.target.value.replace(/\D/g, "").slice(0, 4))} /></label>
        <label className="text-sm font-bold">Mês<select className="mt-2 w-full rounded-lg border border-ink/20 p-3 font-normal" value={month} onChange={(event) => setMonth(event.target.value)}><option value="">Ano inteiro</option>{months.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label>
        <label className="text-sm font-bold sm:col-span-2">Buscar em contratações<input className="mt-2 w-full rounded-lg border border-ink/20 p-3 font-normal" placeholder="Objeto ou órgão" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      </div>
      <p className="mt-4 text-sm leading-6 text-ink/65">Consulta descritiva. Não há classificação automática de irregularidade, e contratação intermunicipal só recebe município quando a fonte o informa.</p>
    </section>

    <section>
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">Siconfi e TCE-SP</p><h2 className="mt-2 text-3xl font-black">Execução e demonstrativos fiscais</h2></div><a className="button-secondary" href={`${API_BASE}/v1/transparency/exports/fiscal-statements.csv?${fiscalCsvQuery}`}>Exportar CSV</a></div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">Cada linha mantém demonstrativo, período, anexo, conta e coluna originais. Receita, empenho, liquidação e pagamento não são somados entre fontes.</p>
      {fiscal.items.length === 0 ? <Empty /> : <div className="mt-5 grid gap-4 lg:grid-cols-2">{fiscal.items.map((item) => <article className="card p-5" key={`${item.source_key}-${item.source.sha256}`}><p className="text-xs font-bold uppercase tracking-wider text-ink/50">{item.source_system} · {item.statement_type.toUpperCase()} · {item.year}{item.period ? ` / período ${item.period}` : ""}</p><h3 className="mt-2 font-extrabold">{item.account.name}</h3><p className="mt-3 text-2xl font-black">{money(item.amount)}</p><p className="mt-2 text-xs text-ink/60">{item.annex} · coluna {item.column ?? "não informada"}</p><SourceLink source={item.source} /></article>)}</div>}
    </section>

    <section>
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">PNCP</p><h2 className="mt-2 text-3xl font-black">Licitações e contratações</h2></div><a className="button-secondary" href={`${API_BASE}/v1/transparency/exports/procurements.csv?${csvQuery}`}>Exportar CSV</a></div>
      <p className="mt-3 text-sm text-ink/65">{procurements.count} registro(s) no recorte publicado; os filtros são aplicados no banco e a API oferece paginação.</p>
      {visible.length === 0 ? <Empty /> : <div className="mt-5 space-y-4">{visible.map((item) => <article className="card p-5" key={item.source_key}><div className="flex flex-wrap justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-ink/50">{item.modality ?? "Modalidade não informada"} · {item.year}</p><h3 className="mt-2 max-w-3xl font-extrabold">{item.object}</h3><p className="mt-2 text-sm text-ink/65">{item.agency} · {item.status ?? "situação não informada"}</p></div><p className="text-xl font-black">{money(item.estimated_amount)}</p></div><SourceLink source={item.source} /></article>)}</div>}
    </section>
  </div>;
}

function SourceLink({ source }: { source: { document_url: string; provider: string; license: string | null; retrieved_at: string } }) {
  return <p className="mt-4 border-t border-ink/10 pt-3 text-xs leading-5 text-ink/60">Fonte: <a className="font-bold underline" href={source.document_url} target="_blank" rel="noreferrer">{source.provider}</a> · licença/status: {source.license ?? "não declarada"} · coletado em {new Intl.DateTimeFormat("pt-BR").format(new Date(source.retrieved_at))}</p>;
}

function Empty() { return <div className="card mt-5 p-6"><p className="font-bold">Nenhum dado publicado para este recorte.</p><p className="mt-2 text-sm text-ink/65">Ausência não é exibida como zero.</p></div>; }

function OverviewCard({ label, value, available }: { label: string; value: string; available: boolean }) { return <article className="card interactive-card border-t-4 border-t-gold p-5"><p className="text-xs font-bold uppercase tracking-wider text-ink/50">{label}</p><p className="mt-3 text-2xl font-black text-[#073f35]">{available ? value : "Não disponível"}</p></article>; }
