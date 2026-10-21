import Link from "next/link";
import { ArrowRightIcon, CircleStackIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { Dashboard } from "@/components/Dashboard";
import { TerritorySearch } from "@/components/TerritorySearch";

export default function Home() {
  return <>
    <section className="grid-lines border-b border-ink/10">
      <div className="container-page py-20">
        <p className="eyebrow">Território, fontes e evidência pública</p>
        <h1 className="mt-5 max-w-5xl text-5xl font-black leading-[0.98] tracking-[-0.045em] sm:text-7xl">Dados do Brasil vistos com <span className="text-teal">clareza</span>, fonte e contexto.</h1>
        <p className="mt-7 max-w-3xl text-lg leading-8 text-ink/70">Encontre qualquer município do diretório IBGE e consulte o catálogo nacional. Gráficos aparecem somente quando há dados efetivamente integrados e publicados.</p>
        <div className="mt-9"><TerritorySearch /></div>
        <div className="mt-5 flex flex-wrap gap-4 text-sm font-bold"><Link href="/buscar" className="text-teal hover:underline">Pesquisa avançada →</Link><Link href="/brasil" className="text-teal hover:underline">Visão nacional →</Link></div>
      </div>
    </section>
    <section className="container-page py-20">
      <div className="mb-9 flex flex-wrap items-end justify-between gap-5"><div><p className="eyebrow">Lente Ribeirão · visão territorial destacada</p><h2 className="mt-3 text-3xl font-black tracking-tight sm:text-5xl">Ribeirão Preto</h2><p className="mt-3 max-w-2xl text-ink/65">A visão que originou o projeto continua disponível dentro da infraestrutura nacional.</p></div><Link href="/municipios/3543402" className="button-secondary gap-2">Abrir perfil completo <ArrowRightIcon className="h-4 w-4" /></Link></div>
      <Dashboard />
    </section>
    <section className="bg-ink py-20 text-white"><div className="container-page grid gap-6 md:grid-cols-3">
      <div className="rounded-2xl border border-white/15 p-7"><CircleStackIcon className="h-9 w-9 text-gold" /><h3 className="mt-5 text-xl font-extrabold">165 candidatos, não 165 integrações</h3><p className="mt-3 text-sm leading-6 text-white/65">O catálogo registra fontes descobertas e mostra separadamente o que já possui conector e dados publicados.</p></div>
      <div className="rounded-2xl border border-white/15 p-7"><ShieldCheckIcon className="h-9 w-9 text-gold" /><h3 className="mt-5 text-xl font-extrabold">Sem preencher lacunas</h3><p className="mt-3 text-sm leading-6 text-white/65">Cidade sem observações homologadas não recebe números simulados. Ausência nunca é exibida como zero.</p></div>
      <div className="rounded-2xl border border-white/15 p-7"><span className="text-3xl font-black text-gold">{`{ }`}</span><h3 className="mt-5 text-xl font-extrabold">API pública</h3><p className="mt-3 text-sm leading-6 text-white/65">Busca, cobertura, séries, JSON, CSV e OpenAPI para conferência e reuso responsável.</p></div>
    </div></section>
  </>;
}
