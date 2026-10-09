import type { Metadata } from "next";
export const metadata: Metadata = { title: "Notícias" };
export default function Page() { return <div className="container-page py-20"><p className="eyebrow">Etapa futura</p><h1 className="mt-3 text-4xl font-black sm:text-6xl">Notícias</h1><p className="mt-6 max-w-2xl text-lg leading-8 text-ink/65">Não há coleta jornalística nem classificação automática de sentimento no MVP. Qualquer módulo futuro terá retenção limitada, atribuição e metodologia explícita.</p></div>; }
