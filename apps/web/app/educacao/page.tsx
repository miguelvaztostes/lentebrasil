import type { Metadata } from "next";
import Link from "next/link";
import { StatusBadge } from "@/components/StatusBadge";

export const metadata: Metadata = { title: "Educação" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Educação</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">IDEB em validação</h1><div className="mt-10 max-w-3xl card p-8"><StatusBadge status="requires_manual_import" /><h2 className="mt-5 text-2xl font-extrabold">O arquivo oficial foi localizado, mas ainda não foi importado.</h2><p className="mt-4 leading-7 text-ink/70">A página do INEP publica resultados municipais de 2005 a 2025. Antes de exibir notas, o pipeline precisa confirmar o arquivo estruturado, suas abas, redes, etapas e códigos de ausência. Nenhuma nota é estimada nesta tela.</p><a href="https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados" target="_blank" rel="noreferrer" className="button-primary mt-7">Abrir fonte oficial</a><Link href="/fontes" className="ml-4 inline-flex text-sm font-bold text-teal hover:underline">Ver auditoria</Link></div></div>;
}

