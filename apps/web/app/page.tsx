import { ArrowRightIcon, CircleStackIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import Link from "next/link";
import { Dashboard } from "@/components/Dashboard";
import { TerritorySearch } from "@/components/TerritorySearch";

function CityComposition() {
  const buildings = [34, 58, 44, 80, 52, 68, 42, 74, 48, 62];
  return (
    <div className="relative min-h-[29rem] overflow-hidden rounded-[2rem] border border-[#073f35]/10 bg-[#e9eee5] shadow-[0_30px_80px_rgba(6,47,41,0.15)]">
      <div className="absolute -right-16 -top-14 h-72 w-72 rounded-full bg-[#e3af42] opacity-95" />
      <div className="absolute -left-24 top-10 h-80 w-80 rounded-full border-[55px] border-[#73a18c]/25" />
      <div className="absolute inset-x-0 bottom-0 h-2/3 bg-[linear-gradient(145deg,transparent_0_28%,rgba(7,63,53,0.07)_28.2%_29%,transparent_29.2%_100%)]" />

      <div className="absolute bottom-0 left-0 right-0 flex h-52 items-end justify-center gap-2 px-7">
        {buildings.map((height, index) => (
          <div key={`${height}-${index}`} className="group relative w-full max-w-12 rounded-t-sm bg-[#0a594a] transition duration-500 hover:-translate-y-2 hover:bg-[#073f35]" style={{ height: `${height}%` }}>
            <div className="grid grid-cols-2 gap-1 p-2 opacity-60">
              {Array.from({ length: Math.max(2, Math.floor(height / 14)) * 2 }).map((_, windowIndex) => <span key={windowIndex} className="h-1.5 bg-[#f2ca61]/75" />)}
            </div>
          </div>
        ))}
      </div>

      <div className="absolute right-7 top-7 max-w-[13rem] rounded-2xl border border-white/70 bg-white/82 p-4 shadow-xl backdrop-blur-md transition duration-300 hover:-translate-y-1 hover:rotate-1">
        <p className="text-[10px] font-black uppercase tracking-[0.15em] text-teal">Do dado à fonte</p>
        <p className="mt-2 text-lg font-black leading-tight text-[#073f35]">Cada número com origem e período.</p>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-ink/10"><div className="h-full w-4/5 rounded-full bg-gold" /></div>
      </div>

      <div className="absolute bottom-7 left-7 rounded-2xl bg-[#073f35] px-5 py-4 text-white shadow-xl transition duration-300 hover:-translate-y-1">
        <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/55">Cobertura</p>
        <p className="mt-1 text-xl font-black">Brasil municipal</p>
        <p className="mt-1 text-xs text-white/60">sem preencher lacunas</p>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <>
      <section className="relative overflow-hidden border-b border-ink/10">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_80%_15%,rgba(17,158,156,0.12),transparent_28rem),radial-gradient(circle_at_12%_78%,rgba(227,175,66,0.12),transparent_24rem)]" />
        <div className="container-page grid min-h-[42rem] items-center gap-12 py-16 lg:grid-cols-[1.04fr_.96fr] lg:py-20">
          <div>
            <div className="flex items-center gap-3 text-[11px] font-bold uppercase tracking-[0.2em] text-[#087875]">
              <span className="h-px w-10 bg-gold" /> Observatório de dados · Brasil
            </div>
            <h1 className="display-title mt-7 max-w-3xl text-6xl leading-[0.9] text-[#073f35] sm:text-7xl xl:text-[5.6rem]">
              Os dados públicos, <em className="font-normal text-teal">em um só lugar.</em>
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-8 text-ink/65 sm:text-lg">
              Indicadores oficiais de saúde, educação, economia, finanças e território, com fonte e ano em cada número — comparáveis quando a metodologia permite.
            </p>
            <div className="mt-9"><TerritorySearch /></div>
            <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
              <span className="mr-1 font-bold text-ink/45">Mais procurados:</span>
              {[
                ["Educação", "/educacao"],
                ["Saúde", "/saude"],
                ["Finanças públicas", "/transparencia"],
                ["Emprego e PIB", "/desenvolvimento"],
              ].map(([label, href]) => <Link key={label} href={href} className="rounded-full border border-ink/12 bg-white/70 px-3 py-1.5 font-semibold transition hover:-translate-y-0.5 hover:border-teal hover:text-teal">{label}</Link>)}
            </div>
          </div>
          <CityComposition />
        </div>
        <div className="border-t border-ink/10 bg-white/65 backdrop-blur">
          <div className="container-page grid divide-y divide-ink/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {[
              ["Território", "Diretório oficial do IBGE"],
              ["Rastreabilidade", "Fonte, coleta e referência"],
              ["Acesso", "API, JSON e CSV"],
            ].map(([label, value]) => <div key={label} className="px-5 py-5 sm:px-8"><p className="text-[10px] font-black uppercase tracking-[0.15em] text-ink/40">{label}</p><p className="mt-1 text-sm font-bold text-[#073f35]">{value}</p></div>)}
          </div>
        </div>
      </section>

      <section className="container-page py-20">
        <div className="mb-9 flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow">Município em destaque</p>
            <h2 className="display-title mt-3 text-4xl sm:text-6xl">Ribeirão Preto</h2>
            <p className="mt-3 max-w-2xl text-ink/65">Um exemplo da leitura municipal disponível no Lente Brasil. Outros municípios podem ser acessados pela busca acima.</p>
          </div>
          <Link href="/municipios/3543402" className="button-secondary gap-2">Abrir perfil completo <ArrowRightIcon className="h-4 w-4" /></Link>
        </div>
        <Dashboard />
      </section>

      <section className="bg-[#073f35] py-20 text-white">
        <div className="container-page grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-white/15 p-7 transition duration-300 hover:-translate-y-1 hover:border-gold/60 hover:bg-white/5"><CircleStackIcon className="h-9 w-9 text-gold" /><h3 className="mt-5 text-xl font-extrabold">165 candidatos, não 165 integrações</h3><p className="mt-3 text-sm leading-6 text-white/65">O catálogo registra fontes descobertas e mostra separadamente o que já possui conector e dados publicados.</p></div>
          <div className="rounded-2xl border border-white/15 p-7 transition duration-300 hover:-translate-y-1 hover:border-gold/60 hover:bg-white/5"><ShieldCheckIcon className="h-9 w-9 text-gold" /><h3 className="mt-5 text-xl font-extrabold">Sem preencher lacunas</h3><p className="mt-3 text-sm leading-6 text-white/65">Cidade sem observações homologadas não recebe números simulados. Ausência nunca é exibida como zero.</p></div>
          <div className="rounded-2xl border border-white/15 p-7 transition duration-300 hover:-translate-y-1 hover:border-gold/60 hover:bg-white/5"><span className="text-3xl font-black text-gold">{`{ }`}</span><h3 className="mt-5 text-xl font-extrabold">API pública</h3><p className="mt-3 text-sm leading-6 text-white/65">Busca, cobertura, séries, JSON, CSV e OpenAPI para conferência e reuso responsável.</p></div>
        </div>
      </section>
    </>
  );
}
