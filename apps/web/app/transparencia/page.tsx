import type { Metadata } from "next";
import { DomainDashboard } from "@/components/DomainDashboard";

export const metadata: Metadata = { title: "Transparência fiscal" };
const codes = ["revenue_realized", "expense_committed", "expense_liquidated", "expense_paid"];
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Finanças públicas</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Transparência</h1><p className="mb-4 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Receita e fases da despesa declaradas no RREO. Empenho, liquidação e pagamento permanecem separados.</p><p className="mb-10 rounded-xl bg-gold/15 p-4 text-sm leading-6">Valores nominais em reais, sujeitos a retificações pelo ente no Siconfi. Não há correção inflacionária nesta versão.</p><DomainDashboard codes={codes} /></div>;
}

