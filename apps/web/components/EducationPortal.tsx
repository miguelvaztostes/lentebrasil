"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { fetchJson, type Municipality } from "@/lib/api";
import { EducationDashboard } from "./EducationDashboard";
import { ErrorState, LoadingState } from "./LoadingState";

const DEFAULT_MUNICIPALITY = "3543402";
const DEMO_MUNICIPALITIES = [DEFAULT_MUNICIPALITY, "3509502", "3550308"];

export function EducationPortal() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("municipio") ?? DEFAULT_MUNICIPALITY;
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchJson<Municipality[]>("/municipalities")
      .then(setMunicipalities)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("pt-BR");
    if (!normalized) return municipalities.filter((item) => DEMO_MUNICIPALITIES.includes(item.ibge_code));
    return municipalities
      .filter((item) => `${item.name} ${item.state} ${item.ibge_code}`.toLocaleLowerCase("pt-BR").includes(normalized))
      .slice(0, 30);
  }, [municipalities, query]);

  if (error) return <ErrorState message={error} />;
  if (!municipalities.length) return <LoadingState label="Carregando municípios…" />;

  const current = municipalities.find((item) => item.ibge_code === code);
  const options = current && !visible.some((item) => item.ibge_code === current.ibge_code)
    ? [current, ...visible]
    : visible;

  return (
    <div>
      <section className="card mb-10 grid gap-4 p-6 md:grid-cols-2">
        <label className="text-sm font-bold">
          Buscar município
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="Nome, UF ou código IBGE" />
        </label>
        <label className="text-sm font-bold">
          Município exibido
          <select value={code} onChange={(event) => router.push(`/educacao?municipio=${event.target.value}`)} className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-4 py-3 font-normal">
            {options.map((item) => <option key={item.ibge_code} value={item.ibge_code}>{item.name}/{item.state} · {item.ibge_code}</option>)}
          </select>
        </label>
        <p className="text-xs leading-5 text-ink/55 md:col-span-2">
          A carga demonstrativa publicada possui dados educacionais para Ribeirão Preto, Campinas e São Paulo. Outros municípios permanecem indisponíveis até uma carga homologada; ausência nunca é tratada como zero.
        </p>
      </section>
      <EducationDashboard code={code} />
    </div>
  );
}
