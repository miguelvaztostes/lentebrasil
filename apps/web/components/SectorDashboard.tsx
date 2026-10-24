"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, fetchJson, type SectorOverview, type SectorSource } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";

const number = (value: string | number | null) => value == null ? "Não disponível" : new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(Number(value));
const money = (value: string | null) => value == null ? "Não disponível" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(Number(value));

export function SectorDashboard({ code, sector }: { code: string; sector: string }) {
  const [data, setData] = useState<SectorOverview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchJson<SectorOverview>(`/sectors/overview?municipality=${encodeURIComponent(code)}`).then(setData).catch((reason: Error) => setError(reason.message)); }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  if (sector === "protecao-social") return <Social data={data} />;
  if (sector === "infraestrutura-e-cidades" || sector === "infraestrutura") return <Infrastructure data={data} />;
  return <EconomyAndLabor data={data} />;
}

function Header({ data, title, description }: { data: SectorOverview; title: string; description: string }) {
  return <header><p className="eyebrow">{data.municipality.name}/{data.municipality.state}</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">{title}</h1><p className="mt-5 max-w-3xl text-lg leading-8 text-ink/65">{description}</p><p className="mt-3 max-w-3xl text-sm font-semibold text-ink/55">{data.notice}</p></header>;
}

function EconomyAndLabor({ data }: { data: SectorOverview }) {
  const pib = [...data.economy.items].filter((item) => item.metric === "gdp_current_prices" && item.value != null).sort((a, b) => b.year - a.year)[0];
  const vab = data.economy.items.filter((item) => item.metric === "gross_value_added" && item.activity?.code !== "TOTAL" && item.value != null).sort((a, b) => a.activity!.label.localeCompare(b.activity!.label));
  const labor = useMemo(() => data.labor.items.map((item) => ({ name: item.section.label, Admissões: item.admissions, Desligamentos: item.dismissals, Saldo: item.balance })).sort((a, b) => Math.abs(b.Saldo) - Math.abs(a.Saldo)).slice(0, 10), [data.labor.items]);
  return <div className="space-y-10"><Header data={data} title="Economia e trabalho" description="PIB municipal anual, composição do valor adicionado e fluxo mensal do emprego formal, preservando períodos e metodologias diferentes." />
    <section className="grid gap-4 md:grid-cols-3"><Metric label={`PIB nominal ${pib?.year ?? ""}`} value={money(pib?.value ?? null)} note="A preços correntes; não corrigido pela inflação." /><Metric label="Admissões · dez/2025" value={number(data.labor.items.reduce((sum, item) => sum + item.admissions, 0) || null)} note="Novo CAGED, fluxo mensal." /><Metric label="Saldo formal · dez/2025" value={data.labor.items.length ? number(data.labor.items.reduce((sum, item) => sum + item.balance, 0)) : "Não disponível"} note="Admissões menos desligamentos; não é estoque." /></section>
    <section className="grid gap-6 xl:grid-cols-2"><article className="card p-6"><h2 className="text-2xl font-black">Valor adicionado por setor</h2><p className="mt-2 text-sm text-ink/60">Último detalhamento completo homologado: 2021, em reais nominais.</p><div className="mt-5 space-y-3">{vab.length ? vab.map((item) => <div key={`${item.year}-${item.activity?.code}`}><div className="flex justify-between gap-4 text-sm"><span>{item.activity?.label}</span><strong>{money(item.value)}</strong></div></div>) : <Empty />}</div></article><article className="card p-6"><h2 className="text-2xl font-black">Movimentações por seção CNAE</h2><p className="mt-2 text-sm text-ink/60">Dezembro/2025. Fluxos podem ser revisados pelo MTE.</p>{labor.length ? <div className="mt-5 h-80"><ResponsiveContainer width="100%" height="100%"><BarChart data={labor} layout="vertical" margin={{ left: 24 }}><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" /><YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 10 }} /><Tooltip /><Legend /><Bar dataKey="Admissões" fill="#0f766e" /><Bar dataKey="Desligamentos" fill="#f59e0b" /></BarChart></ResponsiveContainer></div> : <Empty />}</article></section>
    <Sources data={data} domains={["economy", "labor"]} /></div>;
}

function Infrastructure({ data }: { data: SectorOverview }) {
  const total = data.infrastructure.items.find((item) => item.service.code === "fleet_total");
  const types = data.infrastructure.items.filter((item) => item.service.code !== "fleet_total" && item.value != null).sort((a, b) => Number(b.value) - Number(a.value)).slice(0, 10);
  return <div className="space-y-10"><Header data={data} title="Infraestrutura e cidades" description="Primeira integração homologada do eixo: frota registrada por município e tipo. Saneamento e energia continuam separados até a homologação dos recursos." /><Metric label="Frota registrada · set/2026" value={number(total?.value ?? null)} note="Registro administrativo; não mede circulação diária no município." /><section><h2 className="text-2xl font-black">Tipos de veículo</h2>{types.length ? <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{types.map((item) => <Metric key={item.service.code} label={item.service.label} value={number(item.value)} note={item.unit} />)}</div> : <Empty />}</section><Sources data={data} domains={["infrastructure"]} /></div>;
}

function Social({ data }: { data: SectorOverview }) {
  return <div className="space-y-10"><Header data={data} title="Proteção social" description="Benefícios e cadastros só serão publicados em agregados municipais oficiais, sem listas nominais ou inferências sobre famílias." /><article className="card border-amber-300 bg-amber-50 p-7"><h2 className="text-xl font-black">Dados ainda indisponíveis</h2><p className="mt-3 leading-7 text-ink/70">{data.social.reason}</p><p className="mt-3 text-sm font-semibold">Ausência de carga não significa zero famílias ou zero benefícios.</p></article><div className="grid gap-4 sm:grid-cols-2">{data.social.catalog_sources.map((source) => <article className="card p-5" key={source.id}><p className="eyebrow">{source.id}</p><h3 className="mt-2 font-extrabold">{source.title}</h3><p className="mt-2 text-sm text-ink/60">Fonte candidata · {source.status}</p></article>)}</div></div>;
}

function Sources({ data, domains }: { data: SectorOverview; domains: Array<"economy" | "labor" | "infrastructure"> }) {
  const byDataset = new Map<string, SectorSource>();
  for (const domain of domains) {
    for (const item of data[domain].items) byDataset.set(item.source.dataset, item.source);
  }
  const sources = [...byDataset.values()];
  return <details className="card p-6"><summary className="cursor-pointer font-extrabold">Metodologia, fontes e exportação</summary><div className="mt-5 space-y-4">{domains.map((domain) => <p className="text-sm leading-6 text-ink/65" key={domain}>{data[domain].methodology}</p>)}{sources.map((source) => <div key={source.dataset}><p className="font-bold">{source.provider} · {source.dataset}</p><a className="text-sm font-bold text-teal underline" href={source.url} target="_blank" rel="noreferrer">Artefato oficial</a><span className="mx-2">·</span><span className="text-xs text-ink/50">SHA-256 {source.sha256}</span></div>)}<div className="flex flex-wrap gap-3">{domains.map((domain) => <a className="button-secondary" key={domain} href={`${API_BASE}/v1/sectors/exports/${domain}.csv?municipality=${encodeURIComponent(data.municipality.ibge_code)}`}>Exportar {domain} CSV</a>)}</div></div></details>;
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) { return <article className="card p-5"><p className="text-xs font-bold uppercase tracking-wider text-ink/50">{label}</p><p className="mt-3 text-2xl font-black">{value}</p><p className="mt-3 text-xs leading-5 text-ink/55">{note}</p></article>; }
function Empty() { return <div className="mt-5 rounded-xl border border-dashed border-ink/20 p-5"><p className="font-bold">Não disponível para este recorte.</p><p className="mt-1 text-sm text-ink/60">A ausência não é convertida em zero.</p></div>; }
