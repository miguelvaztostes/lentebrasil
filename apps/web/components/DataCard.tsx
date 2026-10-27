import Link from "next/link";
import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { formatDate, formatValue, type Indicator, type Observation } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

const domainLabels: Record<string, string> = {
  desenvolvimento: "Desenvolvimento",
  educacao: "Educação",
  saude: "Saúde",
  transparencia: "Finanças públicas",
  "financas-publicas": "Finanças públicas",
  "economia-e-trabalho": "Economia e trabalho",
  "infraestrutura-e-cidades": "Infraestrutura e cidades",
};

export function DataCard({ indicator, observation, municipalityCode }: { indicator: Indicator; observation: Observation; municipalityCode?: string }) {
  const value = formatValue(observation.value, indicator.unit);
  return (
    <article className="card interactive-card flex min-w-0 h-full flex-col overflow-hidden p-6">
      <div className="flex items-start justify-between gap-4">
        <p className="eyebrow">{domainLabels[indicator.domain] ?? indicator.domain.replaceAll("-", " ")}</p>
        <StatusBadge status={observation.availability_status} />
      </div>
      <p className="mt-7 max-w-full break-words text-[clamp(1.45rem,2.1vw,2.15rem)] font-black leading-[1.08] tracking-[-0.035em] text-ink [overflow-wrap:anywhere]">
        {value}
      </p>
      <h3 className="mt-2 font-bold">{indicator.label}</h3>
      <p className="mt-2 text-sm text-ink/60">
        Referência {new Date(observation.period_end).getUTCFullYear()} · {indicator.unit}
      </p>
      <div className="mt-6 border-t border-ink/10 pt-4 text-xs leading-5 text-ink/60">
        <p>Coleta: {formatDate(observation.retrieved_at)}</p>
        <a href={observation.source.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex max-w-full items-start gap-1 break-words font-bold text-teal hover:underline [overflow-wrap:anywhere]">
          {observation.source.provider}<ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" />
        </a>
      </div>
      <Link href={`/indicadores/${indicator.code}${municipalityCode ? `?municipality=${municipalityCode}` : ""}`} className="mt-5 text-sm font-bold text-ink hover:text-teal">
        Ver série e metodologia →
      </Link>
    </article>
  );
}

