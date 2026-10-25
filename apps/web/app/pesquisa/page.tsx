import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingState } from "@/components/LoadingState";
import { ResearchWorkbench } from "@/components/ResearchWorkbench";

export const metadata: Metadata = { title: "Pesquisa pública avançada", description: "Explore todos os indicadores municipais publicados, com séries, escopos, fontes e exportação." };

export default function Page() {
  return <div className="container-page py-14"><p className="eyebrow">Pesquisa pública avançada</p><h1 className="mt-3 max-w-5xl text-4xl font-black tracking-tight sm:text-6xl">Todos os dados publicados, em uma consulta reproduzível</h1><p className="mb-10 mt-5 max-w-4xl text-lg leading-8 text-ink/65">Explore fatos de saúde, finanças, economia, trabalho, infraestrutura, agro, educação e proteção social. Escopo e período permanecem explícitos para evitar comparações enganosas.</p><Suspense fallback={<LoadingState />}><ResearchWorkbench /></Suspense></div>;
}
