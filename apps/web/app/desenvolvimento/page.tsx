import type { Metadata } from "next";
import { DomainDashboard } from "@/components/DomainDashboard";

export const metadata: Metadata = { title: "Desenvolvimento" };
const codes = ["population_estimated"];
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Dinâmica municipal</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Desenvolvimento</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Primeira leitura demográfica. Comparações com outros municípios serão liberadas apenas com unidade e metodologia compatíveis.</p><DomainDashboard codes={codes} /></div>;
}
