import type { Metadata } from "next";
import { IndicatorsList } from "@/components/IndicatorsList";

export const metadata: Metadata = { title: "Indicadores" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Catálogo</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Indicadores</h1><p className="mb-10 mt-5 max-w-2xl text-lg leading-8 text-ink/65">Definições, séries, escopo e limitações antes de qualquer comparação.</p><IndicatorsList /></div>;
}

