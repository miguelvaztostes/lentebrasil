"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { fetchJson, type Indicator } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";

type Response = { items: Indicator[]; count: number };
const domains = ["todos", "desenvolvimento", "transparencia", "saude", "educacao"];

export function IndicatorsList() {
  const [items, setItems] = useState<Indicator[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("todos");
  useEffect(() => { fetchJson<Response>("/indicators?limit=100").then((value) => setItems(value.items)).catch((reason: Error) => setError(reason.message)); }, []);
  const filtered = useMemo(() => (items ?? []).filter((item) => (domain === "todos" || item.domain === domain) && item.label.toLowerCase().includes(query.toLowerCase())), [items, query, domain]);
  if (error) return <ErrorState message={error} />;
  if (!items) return <LoadingState />;
  return (
    <div>
      <div className="card grid gap-4 p-5 sm:grid-cols-[1fr_240px]">
        <label className="text-sm font-bold">Buscar indicador<input value={query} onChange={(event) => setQuery(event.target.value)} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="Ex.: população ou despesa" /></label>
        <label className="text-sm font-bold">Área<select value={domain} onChange={(event) => setDomain(event.target.value)} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal">{domains.map((item) => <option key={item} value={item}>{item === "todos" ? "Todas" : item}</option>)}</select></label>
      </div>
      <p className="mt-6 text-sm text-ink/55">{filtered.length} indicador(es) no catálogo</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">{filtered.map((item) => (
        <Link href={`/indicadores/${item.code}`} key={item.code} className="card group p-6 transition hover:-translate-y-0.5 hover:border-teal">
          <span className="eyebrow">{item.domain}</span><h2 className="mt-4 text-xl font-extrabold group-hover:text-teal">{item.label}</h2><p className="mt-3 text-sm leading-6 text-ink/65">{item.definition}</p><div className="mt-5 flex justify-between text-xs font-bold text-ink/50"><span>{item.unit}</span><span>{item.periodicity}</span></div>
        </Link>
      ))}</div>
    </div>
  );
}

