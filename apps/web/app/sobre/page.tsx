import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sobre" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Sobre o Lente Brasil</p><h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">Dados municipais que podem ser conferidos.</h1><div className="mt-10 max-w-3xl space-y-6 text-lg leading-8 text-ink/70"><p>O Lente Brasil é um observatório que organiza dados públicos municipais para tornar fontes, conceitos e limitações mais legíveis. Ribeirão Preto é um dos recortes em destaque, acessível pela mesma busca usada para os demais municípios.</p><p>A plataforma reúne indicadores oficiais em uma experiência consultiva, com período de referência, metodologia, cobertura e ligação para a origem de cada dado publicado.</p><p>Quando uma fonte não oferece formato reutilizável ou não passa pela validação técnica, mostramos a limitação. Lacunas não são preenchidas com estimativas próprias.</p></div></div>;
}

