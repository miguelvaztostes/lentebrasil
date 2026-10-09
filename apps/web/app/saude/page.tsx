import type { Metadata } from "next";
import { DomainDashboard } from "@/components/DomainDashboard";

export const metadata: Metadata = { title: "Saúde" };
const codes = ["cnes_establishments_registered", "cnes_establishments_without_disable_reason", "cnes_establishments_sus_ambulatory"];
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Cadastro de serviços</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Saúde</h1><p className="mb-4 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Leitura agregada do Cadastro Nacional de Estabelecimentos de Saúde para Ribeirão Preto.</p><p className="mb-10 rounded-xl bg-gold/15 p-4 text-sm leading-6">CNES é cadastro declarado. Estes números não medem atendimentos, filas, disponibilidade real ou qualidade assistencial.</p><DomainDashboard codes={codes} /></div>;
}

