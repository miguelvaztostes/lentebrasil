"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRightIcon } from "@heroicons/react/24/outline";
import { ErrorState, LoadingState } from "./LoadingState";
import { SectorIcon } from "./SectorIcon";
import { fetchJson, type MunicipalitySummary } from "@/lib/api";

const sectorContent: Record<string, { label: string; description: string; accent: string }> = {
  "agropecuaria-e-rural": { label: "Agro e produção rural", description: "Culturas, produção, área, rendimento e valor.", accent: "text-[#657b3d] bg-[#657b3d]/10" },
  desenvolvimento: { label: "População e desenvolvimento", description: "Perfil demográfico e indicadores transversais.", accent: "text-teal bg-teal/10" },
  "economia-e-trabalho": { label: "Economia e trabalho", description: "PIB, atividades econômicas e emprego formal.", accent: "text-[#0b6654] bg-[#0b6654]/10" },
  educacao: { label: "Educação", description: "Escolas, matrículas, Ideb, Saeb e PNAE.", accent: "text-[#b17c08] bg-gold/15" },
  "financas-publicas": { label: "Finanças públicas", description: "Receitas, despesas, orçamento e contratos.", accent: "text-[#315f77] bg-[#315f77]/10" },
  "infraestrutura-e-cidades": { label: "Infraestrutura", description: "Frota e serviços urbanos com recorte municipal.", accent: "text-[#4d7180] bg-[#4d7180]/10" },
  saude: { label: "Saúde", description: "Rede, leitos, produção, gastos e epidemiologia.", accent: "text-[#a64747] bg-[#bd5c5c]/10" },
  "territorio-e-demografia": { label: "Território", description: "Limites oficiais e características municipais.", accent: "text-[#48727a] bg-[#48727a]/10" },
};

export function Dashboard({ municipalityCode = "3543402" }: { municipalityCode?: string }) {
  const [data, setData] = useState<MunicipalitySummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<MunicipalitySummary>(`/municipios/${encodeURIComponent(municipalityCode)}/summary`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [municipalityCode]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  const themes = data.sectors
    .filter((sector) => sector.published_datasets > 0 && sectorContent[sector.slug])
    .sort((left, right) => Object.keys(sectorContent).indexOf(left.slug) - Object.keys(sectorContent).indexOf(right.slug));
  return (
    <div>
      <p className="mb-6 max-w-2xl text-sm leading-6 text-ink/60">Escolha uma área para abrir seus indicadores, séries, metodologia e fontes oficiais.</p>
      {!themes.length ? <div className="card p-8"><p className="font-bold">Ainda não há observações validadas para este município.</p><p className="mt-2 text-sm text-ink/65">A interface não exibirá números fictícios enquanto uma fonte oficial não for homologada.</p></div> : null}
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {themes.map((sector) => {
          const content = sectorContent[sector.slug];
          return (
          <Link href={`/municipios/${municipalityCode}/${sector.slug}`} key={sector.slug} className="card interactive-card group relative min-h-60 overflow-hidden p-6">
            <div className={`inline-flex rounded-2xl p-3 ${content.accent} transition duration-300 group-hover:scale-110 group-hover:rotate-[-3deg]`}>
              <SectorIcon slug={sector.slug} className="h-8 w-8" />
            </div>
            <h3 className="mt-7 text-xl font-black tracking-tight text-[#073f35]">{content.label}</h3>
            <p className="mt-3 text-sm leading-6 text-ink/60">{content.description}</p>
            <div className="absolute inset-x-6 bottom-5 flex items-center justify-between border-t border-ink/10 pt-4 text-xs font-bold text-teal">
              <span>Explorar dados</span>
              <ArrowRightIcon className="h-4 w-4 transition duration-300 group-hover:translate-x-1" />
            </div>
          </Link>
          );
        })}
      </div>
      <div className="mt-7 text-right"><Link href={`/municipios/${municipalityCode}`} className="text-sm font-bold text-teal hover:underline">Ver todos os temas, indicadores e fontes →</Link></div>
    </div>
  );
}

