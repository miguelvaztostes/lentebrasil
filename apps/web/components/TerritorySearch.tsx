"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { fetchJson, type Municipality } from "@/lib/api";

type Response = { items: Municipality[]; count: number };

export function TerritorySearch() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Municipality[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setItems([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      fetchJson<Response>(`/geo/municipios?q=${encodeURIComponent(query)}&limit=8`, controller.signal)
        .then((response) => setItems(response.items))
        .catch((error: Error) => error.name !== "AbortError" && setItems([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return (
    <div className="relative max-w-2xl" role="search">
      <label htmlFor="municipality-search" className="sr-only">Buscar município</label>
      <div className="flex rounded-2xl border border-ink/15 bg-white p-2 shadow-card focus-within:border-teal">
        <MagnifyingGlassIcon className="ml-3 mt-3 h-5 w-5 text-ink/45" aria-hidden="true" />
        <input
          id="municipality-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-w-0 flex-1 bg-transparent px-3 py-3 outline-none"
          placeholder="Busque qualquer município do Brasil"
          autoComplete="off"
          aria-controls="municipality-suggestions"
        />
        <Link href={`/buscar?q=${encodeURIComponent(query)}`} className="button-primary">Pesquisar</Link>
      </div>
      {(items.length > 0 || loading) && (
        <div id="municipality-suggestions" className="absolute z-30 mt-2 w-full overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-card">
          {loading && <p className="px-5 py-4 text-sm text-ink/60">Buscando no diretório IBGE…</p>}
          {!loading && items.map((item) => (
            <Link key={item.ibge_code} href={`/municipios/${item.ibge_code}`} className="flex justify-between border-b border-ink/10 px-5 py-4 text-sm hover:bg-teal/10">
              <strong>{item.name}</strong><span>{item.state} · {item.ibge_code}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
