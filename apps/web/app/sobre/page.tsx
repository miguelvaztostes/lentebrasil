import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sobre" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Projeto independente</p><h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">Dados municipais que podem ser conferidos.</h1><div className="mt-10 max-w-3xl space-y-6 text-lg leading-8 text-ink/70"><p>O Lente Brasil organiza dados públicos municipais para tornar fontes, conceitos e limitações mais legíveis. Ribeirão Preto é um dos recortes em destaque, acessível pela mesma busca usada para os demais municípios.</p><p>O projeto se inspira funcionalmente em observatórios cívicos e se alinha ao debate sobre transparência e dados abertos, mas não é um sistema oficial nem afirma parceria com prefeituras, câmaras ou outros órgãos públicos.</p><p>Quando uma fonte não oferece formato reutilizável, mostramos a limitação. Não preenchemos lacunas com estimativas próprias.</p></div></div>;
}

