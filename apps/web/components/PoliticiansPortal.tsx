"use client";

import { BuildingLibraryIcon, MapPinIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { FormEvent, useEffect, useState } from "react";
import { fetchJson } from "@/lib/api";

type Representative = {
  person: { id: string; name: string; ballot_name: string | null; slug: string };
  office: { code: string; name: string; level: string };
  party: string | null;
  territory: { state: string | null; municipality_ibge_code: string | null };
};

type Response = {
  municipality: { ibge_code: string; name: string; state: string };
  items: Representative[];
  coverage: { status: string; message: string };
};

export function PoliticiansPortal() {
  const [requestedCode, setRequestedCode] = useState("3543402");
  const [code, setCode] = useState("3543402");
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    fetchJson<Response>(`/politics/representatives?municipality=${encodeURIComponent(code)}`, controller.signal)
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
    return () => controller.abort();
  }, [code]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (/^\d{7}$/.test(requestedCode)) setCode(requestedCode);
    else setError("Informe um código IBGE municipal com sete dígitos.");
  }

  return <div>
    <form onSubmit={submit} className="card grid gap-4 p-5 sm:grid-cols-[1fr_auto] sm:items-end">
      <label className="text-sm font-bold">Código IBGE do município
        <input aria-label="Código IBGE do município" value={requestedCode} onChange={(event) => setRequestedCode(event.target.value.replace(/\D/g, "").slice(0, 7))} inputMode="numeric" className="mt-2 w-full rounded-xl border border-ink/15 bg-white px-4 py-3 font-mono" placeholder="3543402" />
      </label>
      <button className="button-primary" type="submit">Ver representantes</button>
    </form>

    {error && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {!data && !error && <p className="mt-8 text-sm text-ink/55">Consultando a base oficial…</p>}
    {data && <>
      <section className="mt-10 flex flex-wrap items-end justify-between gap-5 border-b border-ink/10 pb-7">
        <div><p className="eyebrow flex items-center gap-2"><MapPinIcon className="h-4 w-4" /> Município selecionado</p><h2 className="display-title mt-2 text-4xl sm:text-5xl">{data.municipality.name}<span className="text-ink/35">/{data.municipality.state}</span></h2></div>
        <div className="rounded-full bg-teal/10 px-4 py-2 text-xs font-bold text-[#073f35]">{data.items.length} mandato(s) vigente(s)</div>
      </section>
      {data.items.length ? <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{data.items.map((item) => <article key={`${item.person.id}-${item.office.code}`} className="card interactive-card relative overflow-hidden p-6">
        <span className="absolute right-5 top-5 grid h-10 w-10 place-items-center rounded-full bg-[#073f35]/8 text-[#073f35]"><BuildingLibraryIcon className="h-5 w-5" /></span>
        <p className="eyebrow pr-12">{item.office.name}</p>
        <h3 className="mt-4 pr-8 text-xl font-black leading-tight">{item.person.ballot_name || item.person.name}</h3>
        {item.person.ballot_name && <p className="mt-1 text-xs text-ink/45">{item.person.name}</p>}
        <div className="mt-6 flex items-center justify-between border-t border-ink/10 pt-4 text-sm"><span className="font-bold">{item.party || "Partido não informado"}</span><span className="text-ink/45">{item.office.level === "municipal" ? "Municipal" : item.office.level}</span></div>
      </article>)}</div> : <div className="mt-7 rounded-2xl border border-gold/40 bg-gold/10 p-6"><strong>Cobertura indisponível</strong><p className="mt-2 text-sm text-ink/65">{data.coverage.message} Ausência de registro não significa ausência de representante.</p></div>}
    </>}

    <aside className="mt-12 grid gap-5 rounded-2xl bg-[#073f35] p-7 text-white md:grid-cols-[auto_1fr]">
      <ShieldCheckIcon className="h-9 w-9 text-[#f2ca61]" />
      <div><h2 className="text-2xl font-black">Leitura responsável</h2><p className="mt-3 max-w-4xl text-sm leading-6 text-white/70">A relação usa resultados oficiais do TSE. Bens são publicados somente em totais por categoria; CPF, e-mail, título eleitoral, data de nascimento, endereços e descrições livres não são armazenados. Futuras notas de atuação só serão comparáveis no mesmo cargo, período e metodologia, com cobertura mínima declarada.</p></div>
    </aside>
  </div>;
}
