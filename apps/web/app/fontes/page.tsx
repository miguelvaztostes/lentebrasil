import type { Metadata } from "next";
import { SourcesList } from "@/components/SourcesList";

export const metadata: Metadata = { title: "Fontes" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Rastreabilidade</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Fontes verificadas</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Acessibilidade técnica, frequência, licença conhecida e impedimentos ficam visíveis — inclusive quando uma integração ainda não está pronta.</p><SourcesList /></div>;
}

