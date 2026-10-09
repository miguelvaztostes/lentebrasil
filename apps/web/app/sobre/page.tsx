import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sobre" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Projeto independente</p><h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">Dados municipais que podem ser conferidos.</h1><div className="mt-10 max-w-3xl space-y-6 text-lg leading-8 text-ink/70"><p>O Lente Ribeirão organiza dados públicos de Ribeirão Preto para tornar fontes, conceitos e limitações mais legíveis. Começa pequeno, com integrações comprovadas, e foi estruturado para receber outros municípios no futuro.</p><p>O projeto se inspira funcionalmente em observatórios cívicos e se alinha ao debate local sobre transparência e dados abertos, mas não é um sistema oficial nem afirma parceria com Prefeitura, Câmara, Instituto Ribeirão 2030 ou Lente Brasil.</p><p>Quando uma fonte não oferece formato reutilizável, mostramos a limitação. Não preenchemos lacunas com estimativas próprias.</p></div></div>;
}

