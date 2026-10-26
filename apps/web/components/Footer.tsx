import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-24 border-t border-ink/10 bg-ink text-white">
      <div className="container-page grid gap-10 py-12 md:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <p className="text-xl font-extrabold">Lente Brasil</p>
          <p className="mt-3 max-w-lg text-sm leading-6 text-white/70">
            Observatório cívico independente de dados públicos. Não representa oficialmente a Prefeitura,
            a Câmara, o Instituto Ribeirão 2030 ou qualquer órgão público.
          </p>
        </div>
        <div className="grid content-start gap-3 text-sm">
          <p className="font-bold text-gold">Entenda os dados</p>
          <Link href="/metodologia" className="text-white/70 hover:text-white">Metodologia</Link>
          <Link href="/fontes" className="text-white/70 hover:text-white">Fontes</Link>
          <Link href="/dados-abertos" className="text-white/70 hover:text-white">API e downloads</Link>
          <Link href="/contribuir/fonte" className="text-white/70 hover:text-white">Sugerir uma fonte</Link>
        </div>
        <div className="grid content-start gap-3 text-sm">
          <p className="font-bold text-gold">Projeto</p>
          <Link href="/sobre" className="text-white/70 hover:text-white">Sobre</Link>
          <Link href="/privacidade" className="text-white/70 hover:text-white">Privacidade</Link>
          <Link href="/municipios/3543402" className="text-white/70 hover:text-white">Visão Lente Ribeirão</Link>
        </div>
      </div>
    </footer>
  );
}

