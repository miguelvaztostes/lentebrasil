import type { Metadata } from "next";
import { CuratorConsole } from "@/components/CuratorConsole";

export const metadata: Metadata = { title: "Curadoria", robots: { index: false, follow: false } };

export default function Page() {
  return <div className="container-page py-14"><p className="eyebrow">Backoffice protegido</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Fila de curadoria</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">A API valida o token no IdP, exige MFA e aplica os papéis curator, data_steward e admin em cada transição. Esta tela não armazena credenciais.</p><CuratorConsole /></div>;
}
