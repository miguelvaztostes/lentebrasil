"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "./LoadingState";
import { fetchJson, type SchoolDetailResponse } from "@/lib/api";

export function SchoolDetail({ code }: { code: string }) {
  const [data, setData] = useState<SchoolDetailResponse | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchJson<SchoolDetailResponse>(`/education/schools/${encodeURIComponent(code)}`).then(setData).catch((reason: Error) => setError(reason.message)); }, [code]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  return <div><p className="eyebrow">Escola · código Inep {data.inep_code}</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">{data.name}</h1><p className="mt-4 text-ink/65">Censo Escolar {data.year} · dependência {data.dependency_code} · situação {data.operating_status}</p><section className="card mt-10 p-7"><h2 className="text-xl font-extrabold">Matrículas por etapa</h2><div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{data.enrollments.map((item) => <div key={item.stage}><p className="text-xs text-ink/55">{item.stage.replaceAll("_", " ")}</p><p className="text-2xl font-black">{item.value == null ? "Indisponível" : item.value.toLocaleString("pt-BR")}</p></div>)}</div></section><section className="card mt-6 p-7"><h2 className="text-xl font-extrabold">Infraestrutura declarada</h2><div className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(data.infrastructure).map(([key, value]) => <p key={key} className="text-sm"><strong>{key.replaceAll("_", " ")}:</strong> {value == null ? "não informado" : value ? "sim" : "não"}</p>)}</div></section><p className="mt-6 text-xs text-ink/55">Fonte: <a className="font-bold text-teal underline" href={data.source.url ?? "#"} target="_blank" rel="noreferrer">Inep</a>. A plataforma não armazena endereço, telefone, CNPJ nem dados individuais.</p><Link className="button-secondary mt-8" href={`/municipios/${data.municipality_ibge_code}/educacao`}>Voltar à educação municipal</Link></div>;
}
