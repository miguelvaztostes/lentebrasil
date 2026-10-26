import type { Metadata } from "next";
import { SourceContributionForm } from "@/components/SourceContributionForm";

export const metadata: Metadata = { title: "Sugerir uma fonte", description: "Envie uma fonte pública para triagem humana, sem publicação automática." };

export default function Page() {
  return <div className="container-page py-14"><p className="eyebrow">Contribuição pública</p><h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">Ajude a descobrir dados municipais</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Indique uma API, arquivo ou portal oficial. A sugestão não é tratada como fonte homologada e nunca aciona coleta automática: curadores verificam origem, licença, privacidade, schema e qualidade antes de qualquer publicação.</p><div className="max-w-4xl"><SourceContributionForm /></div></div>;
}
