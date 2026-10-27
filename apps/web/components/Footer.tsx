import Link from "next/link";

export function Footer() {
  return (
    <footer className="relative mt-24 overflow-hidden border-t border-white/10 bg-[#06131f] text-white">
      <div aria-hidden="true" className="pointer-events-none absolute -right-32 -top-36 h-96 w-96 rounded-full border border-teal/15" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full border border-gold/10" />

      <div className="container-page relative grid gap-12 py-14 lg:grid-cols-[1.45fr_.8fr_.8fr] lg:py-16">
        <div>
          <Link href="/" aria-label="Lente Brasil — página inicial" className="group inline-flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-full border border-white/15 bg-white/[0.06] text-teal transition duration-300 group-hover:rotate-6 group-hover:border-teal/50 group-hover:bg-teal/10">
              <svg aria-hidden="true" viewBox="0 0 32 32" className="h-7 w-7 fill-none stroke-current" strokeWidth="2">
                <circle cx="14" cy="14" r="8" />
                <path d="m20 20 7 7M7.5 15.5c2.1-2.7 4.4-3.9 6.8-3.5 1.8.3 3.1 1.3 4.2 2.5" />
                <circle cx="10" cy="16" r="1" className="fill-current stroke-none" />
                <circle cx="15" cy="11.8" r="1" className="fill-current stroke-none" />
                <circle cx="18.5" cy="15" r="1" className="fill-current stroke-none" />
              </svg>
            </span>
            <span className="display-title text-2xl text-white">Lente <em>Brasil</em></span>
          </Link>
          <p className="mt-5 max-w-xl text-base leading-7 text-white/68">
            Observatório de dados públicos municipais. Indicadores oficiais organizados com contexto,
            metodologia e rastreabilidade para apoiar análises e decisões.
          </p>
          <div className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-[11px] font-bold uppercase tracking-[0.14em] text-white/45">
            <span>Fontes oficiais</span>
            <span>Metodologia aberta</span>
            <span>API pública</span>
          </div>
        </div>

        <nav aria-label="Dados e metodologia" className="grid content-start gap-3 text-sm">
          <p className="mb-1 text-xs font-black uppercase tracking-[0.16em] text-gold">Explore</p>
          <Link href="/indicadores" className="text-white/65 transition hover:translate-x-1 hover:text-white">Indicadores</Link>
          <Link href="/brasil" className="text-white/65 transition hover:translate-x-1 hover:text-white">Municípios e regiões</Link>
          <Link href="/comparar" className="text-white/65 transition hover:translate-x-1 hover:text-white">Comparar territórios</Link>
          <Link href="/pesquisa" className="text-white/65 transition hover:translate-x-1 hover:text-white">Pesquisa avançada</Link>
        </nav>

        <nav aria-label="Informações do projeto" className="grid content-start gap-3 text-sm">
          <p className="mb-1 text-xs font-black uppercase tracking-[0.16em] text-gold">Transparência</p>
          <Link href="/metodologia" className="text-white/65 transition hover:translate-x-1 hover:text-white">Metodologia</Link>
          <Link href="/fontes" className="text-white/65 transition hover:translate-x-1 hover:text-white">Fontes e cobertura</Link>
          <Link href="/dados-abertos" className="text-white/65 transition hover:translate-x-1 hover:text-white">API e downloads</Link>
          <Link href="/privacidade" className="text-white/65 transition hover:translate-x-1 hover:text-white">Privacidade e LGPD</Link>
        </nav>
      </div>

      <div className="border-t border-white/10">
        <div className="container-page relative flex flex-col gap-7 py-7 md:flex-row md:items-center md:justify-between">
          <a
            href="https://vazdeveloper.com.br/"
            target="_blank"
            rel="noreferrer"
            aria-label="Visitar o site da Vaz Developer"
            className="group inline-flex w-fit items-center gap-3 rounded-xl transition hover:text-[#50c99b]"
          >
            <span className="grid h-10 w-10 place-items-center rounded-lg border border-[#50c99b]/35 bg-[#50c99b]/10 font-mono text-sm font-black text-[#50c99b] transition group-hover:-translate-y-0.5 group-hover:border-[#50c99b]">
              {"</>"}
            </span>
            <span>
              <span className="block text-[10px] font-bold uppercase tracking-[0.17em] text-white/40">Tecnologia e desenvolvimento</span>
              <span className="mt-0.5 block text-base font-extrabold">Vaz <span className="text-[#50c99b]">Developer</span> <span aria-hidden="true">↗</span></span>
            </span>
          </a>

          <div className="text-xs leading-5 text-white/45 md:text-right">
            <p>© {new Date().getFullYear()} Lente Brasil</p>
            <p>Origem, atualização e licença informadas em cada conjunto de dados.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}

