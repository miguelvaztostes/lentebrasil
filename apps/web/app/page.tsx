import Link from "next/link";
import { ArrowRightIcon, CircleStackIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { Dashboard } from "@/components/Dashboard";

export default function Home() {
  return (
    <>
      <section className="grid-lines border-b border-ink/10">
        <div className="container-page grid min-h-[560px] items-center gap-12 py-16 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <p className="eyebrow">Ribeirão Preto · dados públicos com contexto</p>
            <h1 className="mt-5 max-w-4xl text-5xl font-black leading-[0.98] tracking-[-0.045em] sm:text-7xl">
              O município visto com <span className="text-teal">clareza</span>, fonte e método.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-ink/70">
              Explore séries oficiais, acompanhe quando foram coletadas e chegue ao documento de origem de cada número.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link href="/indicadores" className="button-primary gap-2">Explorar indicadores <ArrowRightIcon className="h-4 w-4" /></Link>
              <Link href="/metodologia" className="button-secondary">Como tratamos os dados</Link>
            </div>
          </div>
          <div className="relative mx-auto aspect-square w-full max-w-md overflow-hidden rounded-full border border-ink/10 bg-white shadow-card">
            <div className="absolute inset-[12%] rounded-full border-[22px] border-ink" />
            <div className="absolute left-[22%] top-[24%] h-[42%] w-[42%] rounded-full bg-teal" />
            <div className="absolute left-[8%] right-[8%] top-1/2 h-20 -rotate-6 rounded-[50%] border-y-[12px] border-white bg-transparent" />
            <div className="absolute right-[12%] top-[12%] grid grid-cols-2 gap-2"><i className="h-5 w-5 bg-teal" /><i className="h-7 w-7 bg-gold" /><i className="h-3 w-3 bg-teal" /></div>
            <p className="absolute bottom-[13%] left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-black uppercase tracking-[0.28em] text-ink/50">evidência pública</p>
          </div>
        </div>
      </section>
      <section className="container-page py-20">
        <div className="mb-9 flex flex-wrap items-end justify-between gap-5">
          <div><p className="eyebrow">Retrato disponível</p><h2 className="mt-3 text-3xl font-black tracking-tight sm:text-5xl">Indicadores com coleta comprovada</h2></div>
          <Link href="/fontes" className="text-sm font-bold text-teal hover:underline">Auditar as fontes →</Link>
        </div>
        <Dashboard />
      </section>
      <section className="bg-ink py-20 text-white">
        <div className="container-page grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-white/15 p-7"><CircleStackIcon className="h-9 w-9 text-gold" /><h3 className="mt-5 text-xl font-extrabold">Histórico preservado</h3><p className="mt-3 text-sm leading-6 text-white/65">Revisões não apagam valores anteriores. Cada carga tem hash, momento e origem.</p></div>
          <div className="rounded-2xl border border-white/15 p-7"><ShieldCheckIcon className="h-9 w-9 text-gold" /><h3 className="mt-5 text-xl font-extrabold">Sem preencher lacunas</h3><p className="mt-3 text-sm leading-6 text-white/65">Dado ausente permanece ausente. Zero só aparece quando a fonte realmente informa zero.</p></div>
          <div className="rounded-2xl border border-white/15 p-7"><span className="text-3xl font-black text-gold">{`{ }`}</span><h3 className="mt-5 text-xl font-extrabold">API pública</h3><p className="mt-3 text-sm leading-6 text-white/65">JSON, CSV e documentação OpenAPI para conferência e reuso responsável.</p></div>
        </div>
      </section>
    </>
  );
}

