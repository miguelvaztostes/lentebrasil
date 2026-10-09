import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacidade" };
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">LGPD e segurança</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Privacidade</h1><div className="mt-10 max-w-3xl space-y-5 text-base leading-7 text-ink/70"><p>O MVP publica dados públicos agregados e não exige cadastro de visitantes. Logs técnicos não devem registrar dados pessoais, parâmetros sensíveis ou conteúdo integral das fontes.</p><p>O arquivo oficial do CNES contém nomes e contatos de estabelecimentos. O coletor calcula agregados em memória e persiste somente contagens, hash e URL do recurso; esses campos de contato não são copiados para a base analítica.</p><p>Segredos ficam em variáveis de ambiente do backend. Em produção, o banco não deve ser exposto e o acesso público deve usar HTTPS.</p></div></div>;
}

