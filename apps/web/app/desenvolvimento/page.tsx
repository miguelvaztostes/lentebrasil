import type { Metadata } from "next";
import { DomainDashboard } from "@/components/DomainDashboard";
import { SectorDashboard } from "@/components/SectorDashboard";
import { AgricultureDashboard } from "@/components/AgricultureDashboard";
import Link from "next/link";

export const metadata: Metadata = { title: "Desenvolvimento" };
const codes = ["population_estimated"];
export default function Page() {
  return <div className="container-page space-y-16 py-16"><section><p className="eyebrow">Dinâmica municipal</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Desenvolvimento</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">População, economia, emprego formal, infraestrutura e produção rural publicados em seus períodos e metodologias próprios.</p><DomainDashboard codes={codes} /><div className="mt-6 flex flex-wrap gap-3"><Link href="/comparar?indicador=economy:gdp_current_prices" className="button-primary">Comparar PIB municipal</Link><Link href="/pesquisa" className="button-secondary">Abrir pesquisa completa</Link></div></section><SectorDashboard code="3543402" sector="economia-e-trabalho" /><SectorDashboard code="3543402" sector="infraestrutura-e-cidades" /><AgricultureDashboard code="3543402" /></div>;
}
