import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingState } from "@/components/LoadingState";
import { ResearchWorkbench } from "@/components/ResearchWorkbench";

export const metadata: Metadata = { title: "Comparar municípios", description: "Compare municípios somente no mesmo indicador, escopo, unidade e período." };

export default function Page() {
  return <div className="container-page py-14"><p className="eyebrow">Comparador municipal</p><h1 className="mt-3 max-w-5xl text-4xl font-black tracking-tight sm:text-6xl">Compare territórios sem misturar conceitos</h1><p className="mb-10 mt-5 max-w-4xl text-lg leading-8 text-ink/65">A comparação só é desenhada quando indicador, unidade, escopo e referência são compatíveis. Ausência, sigilo ou falta de cobertura nunca aparecem como zero.</p><Suspense fallback={<LoadingState />}><ResearchWorkbench compareMode /></Suspense></div>;
}
