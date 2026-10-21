"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { fetchJson, type SearchResponse } from "@/lib/api";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

const statusOptions = [
  ["", "Todos"], ["discovered", "Descoberta"], ["pending_review", "Em revisão"],
  ["integrated", "Integrada"], ["published", "Dados publicados"], ["stale", "Desatualizada"],
  ["restricted", "Restrita"], ["unavailable", "Indisponível"],
];

export function SearchPortal() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const queryString = searchParams.toString();

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchJson<SearchResponse>(`/search?${queryString}`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [queryString]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const params = new URLSearchParams();
    for (const [key, value] of form.entries()) {
      if (String(value).trim()) params.set(key, String(value).trim());
    }
    router.push(`/buscar?${params.toString()}`);
  }

  return (
    <div>
      <form onSubmit={submit} className="card grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" role="search">
        <label className="text-sm font-bold md:col-span-2">Texto livre
          <input name="q" defaultValue={searchParams.get("q") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="Município, fonte, tema ou indicador" />
        </label>
        <label className="text-sm font-bold">UF
          <input name="uf" defaultValue={searchParams.get("uf") ?? ""} maxLength={2} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 uppercase font-normal" placeholder="SP" />
        </label>
        <label className="text-sm font-bold">Setor
          <select name="sector" defaultValue={searchParams.get("sector") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todos</option>{data?.facets.sectors.map((facet) => <option key={facet.value} value={facet.value}>{facet.value} ({facet.count})</option>)}</select>
        </label>
        <label className="text-sm font-bold">Origem
          <select name="origin" defaultValue={searchParams.get("origin") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todas</option>{data?.facets.providers.map((facet) => <option key={facet.value} value={facet.value}>{facet.value} ({facet.count})</option>)}</select>
        </label>
        <label className="text-sm font-bold">Recurso
          <select name="resource" defaultValue={searchParams.get("resource") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todos</option>{data?.facets.resources.map((facet) => <option key={facet.value} value={facet.value}>{facet.value} ({facet.count})</option>)}</select>
        </label>
        <label className="text-sm font-bold">Formato
          <select name="format" defaultValue={searchParams.get("format") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todos</option>{data?.facets.formats.map((facet) => <option key={facet.value} value={facet.value}>{facet.value} ({facet.count})</option>)}</select>
        </label>
        <label className="text-sm font-bold">Granularidade
          <input name="granularity" defaultValue={searchParams.get("granularity") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="Município / ano" />
        </label>
        <label className="text-sm font-bold">Estado
          <select name="status" defaultValue={searchParams.get("status") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal">{statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </label>
        <label className="text-sm font-bold">Disponibilidade
          <select name="availability" defaultValue={searchParams.get("availability") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todas</option><option value="published">Com dados publicados</option><option value="not_published">Sem dados publicados</option></select>
        </label>
        <label className="text-sm font-bold">Licença
          <select name="license_status" defaultValue={searchParams.get("license_status") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todas</option>{data?.facets.license_statuses.map((facet) => <option key={facet.value} value={facet.value}>{facet.value} ({facet.count})</option>)}</select>
        </label>
        <label className="text-sm font-bold">Atualidade
          <select name="freshness" defaultValue={searchParams.get("freshness") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal"><option value="">Todas</option><option value="current">Verificada recentemente</option><option value="stale">Verificação antiga</option><option value="unknown">Não verificada</option></select>
        </label>
        <label className="text-sm font-bold">Período inicial
          <input name="from_year" inputMode="numeric" defaultValue={searchParams.get("from_year") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="2020" />
        </label>
        <label className="text-sm font-bold">Período final
          <input name="to_year" inputMode="numeric" defaultValue={searchParams.get("to_year") ?? ""} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="2026" />
        </label>
        <button className="button-primary self-end">Aplicar filtros</button>
      </form>

      {data && <div className="mt-6 grid gap-4 sm:grid-cols-3"><div className="card p-5"><strong className="text-3xl">{data.summary.candidate_sources}</strong><p className="text-sm text-ink/60">fontes candidatas catalogadas</p></div><div className="card p-5"><strong className="text-3xl">{data.summary.published_datasets}</strong><p className="text-sm text-ink/60">recursos com observações publicadas</p></div><div className="card p-5"><strong className="text-3xl">{data.count}</strong><p className="text-sm text-ink/60">resultados nos filtros atuais</p></div></div>}
      <p className="mt-4 text-xs text-ink/55">Fonte descoberta, integração técnica e dado publicado são estados separados.</p>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}
      {loading && <div className="mt-6"><LoadingState label="Consultando catálogo e diretório territorial…" /></div>}
      {!loading && data && (
        <div className="mt-8 grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside><h2 className="text-lg font-extrabold">Municípios encontrados</h2><div className="mt-3 grid gap-2">{data.municipalities.map((item) => <Link key={item.ibge_code} href={`/municipios/${item.ibge_code}`} className="rounded-xl border border-ink/10 bg-white p-4 text-sm hover:border-teal"><strong className="block">{item.name}</strong><span className="text-ink/55">{item.state} · {item.ibge_code}</span></Link>)}</div>{!data.municipalities.length && <p className="mt-3 text-sm text-ink/55">Nenhum município corresponde ao texto e à UF.</p>}</aside>
          <section aria-live="polite"><h2 className="text-lg font-extrabold">Catálogo nacional</h2>{!data.items.length ? <p className="card mt-3 p-6 text-sm">Nenhum registro corresponde aos filtros. Isso não significa valor zero nem ausência definitiva da fonte.</p> : <div className="mt-3 grid gap-4">{data.items.map((item) => <article key={item.id} className="card p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow">{item.id} · {item.area_label}</p><h3 className="mt-2 text-xl font-extrabold">{item.title}</h3></div><StatusBadge status={item.status} /></div><p className="mt-3 text-sm leading-6 text-ink/65">{item.description}</p><dl className="mt-5 grid gap-3 text-xs sm:grid-cols-3"><div><dt className="font-bold text-ink/50">Origem</dt><dd>{item.provider.name}</dd></div><div><dt className="font-bold text-ink/50">Formato</dt><dd>{item.resource?.format ?? "não confirmado"}</dd></div><div><dt className="font-bold text-ink/50">Cobertura</dt><dd>{item.dataset?.granularity ?? "em revisão"}</dd></div></dl><div className="mt-5 flex flex-wrap gap-4"><Link href={`/fontes/${item.id}`} className="text-sm font-bold text-teal hover:underline">Ver contexto e proveniência</Link>{item.resource?.url && <a href={item.resource.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-bold text-teal hover:underline">Fonte indicada <ArrowTopRightOnSquareIcon className="h-4 w-4" /></a>}</div></article>)}</div>}</section>
        </div>
      )}
    </div>
  );
}
