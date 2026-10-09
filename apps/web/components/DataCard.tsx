import Link from "next/link";
import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { formatDate, formatValue, type Indicator, type Observation } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

export function DataCard({ indicator, observation }: { indicator: Indicator; observation: Observation }) {
  return (
    <article className="card flex h-full flex-col p-6">
      <div className="flex items-start justify-between gap-4">
        <p className="eyebrow">{indicator.domain}</p>
        <StatusBadge status={observation.availability_status} />
      </div>
      <p className="mt-7 text-3xl font-black tracking-tight text-ink sm:text-4xl">
        {formatValue(observation.value, indicator.unit)}
      </p>
      <h3 className="mt-2 font-bold">{indicator.label}</h3>
      <p className="mt-2 text-sm text-ink/60">
        Referência {new Date(observation.period_end).getUTCFullYear()} · {indicator.unit}
      </p>
      <div className="mt-6 border-t border-ink/10 pt-4 text-xs leading-5 text-ink/60">
        <p>Coleta: {formatDate(observation.retrieved_at)}</p>
        <a href={observation.source.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 font-bold text-teal hover:underline">
          {observation.source.provider}<ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" />
        </a>
      </div>
      <Link href={`/indicadores/${indicator.code}`} className="mt-5 text-sm font-bold text-ink hover:text-teal">
        Ver série e metodologia →
      </Link>
    </article>
  );
}

