import type { Metadata } from "next";
import { TransparencyDashboard } from "@/components/TransparencyDashboard";

export const metadata: Metadata = { title: "Transparência fiscal" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Finanças públicas</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Transparência e contratações</h1><p className="mb-4 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Demonstrativos fiscais, receitas e contratações oficiais com histórico de versões, filtros e acesso ao documento de origem.</p><p className="mb-10 rounded-xl bg-gold/15 p-4 text-sm leading-6">Valores nominais em reais, sujeitos a republicações. Fases contábeis e períodos acumulados permanecem separados; o painel não produz acusações automáticas.</p><TransparencyDashboard /></div>;
}

