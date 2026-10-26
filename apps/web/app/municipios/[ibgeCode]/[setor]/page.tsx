import type { Metadata } from "next";
import { MunicipalitySector } from "@/components/MunicipalitySector";

const sectorTitles: Record<string, string> = {
  "agropecuaria-e-rural": "Agropecuária e rural",
  "economia-e-trabalho": "Economia e trabalho",
  educacao: "Educação",
  "financas-publicas": "Finanças públicas",
  "infraestrutura-e-cidades": "Infraestrutura e cidades",
  "meio-ambiente-e-riscos": "Meio ambiente e riscos",
  "participacao-e-democracia": "Participação e democracia",
  "protecao-social": "Proteção social",
  saude: "Saúde",
  "seguranca-publica": "Segurança pública",
  "territorio-e-demografia": "Território e demografia",
};

export async function generateMetadata({ params }: { params: Promise<{ ibgeCode: string; setor: string }> }): Promise<Metadata> {
  const { ibgeCode, setor } = await params;
  const title = sectorTitles[setor] ?? setor.replaceAll("-", " ");
  return { title: `${title} · ${ibgeCode}` };
}
export default async function Page({ params }: { params: Promise<{ ibgeCode: string; setor: string }> }) { const { ibgeCode, setor } = await params; return <div className="container-page py-16"><MunicipalitySector code={ibgeCode} sector={setor} /></div>; }
