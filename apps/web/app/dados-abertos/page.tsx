import type { Metadata } from "next";
import { API_BASE } from "@/lib/api";
import { PipelinesStatus } from "@/components/PipelinesStatus";

export const metadata: Metadata = { title: "Dados abertos" };
const endpoints = [
  ["Municípios", "/v1/municipalities"], ["Fontes", "/v1/sources"], ["Datasets", "/v1/datasets"],
  ["Indicadores", "/v1/indicators"], ["Resumo", "/v1/dashboard/summary"], ["Pipelines", "/v1/pipelines/status"],
];
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Reuso responsável</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Dados abertos</h1><p className="mt-5 max-w-3xl text-lg leading-8 text-ink/65">API pública sem login, exportação CSV por indicador e metadados de proveniência no próprio resultado.</p><div className="mt-10 grid gap-6 lg:grid-cols-2"><section className="card p-7"><h2 className="text-2xl font-extrabold">Endpoints JSON</h2><div className="mt-5 grid gap-3">{endpoints.map(([label, path]) => <a key={path} href={`${API_BASE}${path}`} className="flex items-center justify-between rounded-xl bg-paper px-4 py-3 font-mono text-xs hover:bg-teal/10"><span>{label}</span><code>{path}</code></a>)}</div><a href={`${API_BASE}/docs`} className="button-primary mt-6">Abrir documentação OpenAPI</a></section><section className="card p-7"><h2 className="text-2xl font-extrabold">Exportação CSV</h2><p className="mt-4 text-sm leading-6 text-ink/65">Use <code className="rounded bg-paper px-2 py-1">/api/v1/exports/observations.csv?indicator=código</code>. O arquivo inclui período, escopo, unidade, revisão, URL e hash do snapshot.</p><h3 className="mt-7 font-extrabold">Limites</h3><ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-ink/65"><li>Máximo de 2.000 linhas por consulta JSON.</li><li>Máximo de 10.000 linhas por exportação CSV.</li><li>Datas são armazenadas em UTC e exibidas em America/Sao_Paulo.</li></ul></section></div><section className="mt-16"><p className="eyebrow">Monitoramento público</p><h2 className="mb-7 mt-3 text-3xl font-black">Estado das integrações</h2><PipelinesStatus /></section></div>;
}

