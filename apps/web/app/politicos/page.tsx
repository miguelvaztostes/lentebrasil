import type { Metadata } from "next";
import { PoliticiansPortal } from "@/components/PoliticiansPortal";

export const metadata: Metadata = { title: "Representantes políticos" };

export default function Page() {
  return <div className="container-page py-16">
    <p className="eyebrow">Representação pública</p>
    <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">Quem representa seu município</h1>
    <p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Mandatos eleitos organizados por território, cargo e partido, com rastreabilidade até a fonte eleitoral oficial. A cobertura nacional será aberta município a município após validação da carga.</p>
    <PoliticiansPortal />
  </div>;
}
