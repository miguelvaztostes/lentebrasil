"use client";

import { ArrowUpRightIcon, CheckCircleIcon, CircleStackIcon, MapPinIcon } from "@heroicons/react/24/outline";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DataCard } from "./DataCard";
import { ErrorState, LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";
import { SectorIcon } from "./SectorIcon";
import { fetchJson, type MunicipalitySummary } from "@/lib/api";

const sectorContent: Record<string, { label: string; description: string; accent: string }> = {
  "agropecuaria-e-rural": { label: "Agropecuária e rural", description: "Produção agrícola e pecuária municipal.", accent: "bg-[#657b3d]" },
  "catalogos-e-descoberta": { label: "Catálogos e descoberta", description: "Fontes mapeadas e recursos em avaliação.", accent: "bg-[#53738b]" },
  "ciencia-e-inovacao": { label: "Ciência e inovação", description: "Pesquisa, tecnologia e capacidade de inovação.", accent: "bg-[#735e91]" },
  "cultura-e-turismo": { label: "Cultura e turismo", description: "Equipamentos, patrimônio e atividade turística.", accent: "bg-[#b1664b]" },
  desenvolvimento: { label: "Desenvolvimento", description: "Indicadores transversais do município.", accent: "bg-[#119e9c]" },
  "economia-e-trabalho": { label: "Economia e trabalho", description: "PIB, atividades econômicas e emprego formal.", accent: "bg-[#0b6654]" },
  educacao: { label: "Educação", description: "Escolas, matrículas, Ideb, Saeb e alimentação escolar.", accent: "bg-[#d7a329]" },
  "financas-publicas": { label: "Finanças públicas", description: "Orçamento, receitas, despesas e transferências.", accent: "bg-[#315f77]" },
  "gestao-publica": { label: "Gestão pública", description: "Capacidade institucional e serviços públicos.", accent: "bg-[#6c7480]" },
  "meio-ambiente-e-riscos": { label: "Meio ambiente e riscos", description: "Território, clima e riscos ambientais.", accent: "bg-[#4d785a]" },
  "municipal-ribeirao-preto": { label: "Dados locais de Ribeirão Preto", description: "Recursos oficiais específicos do município.", accent: "bg-[#aa713c]" },
  "participacao-e-democracia": { label: "Participação e democracia", description: "Participação social, eleições e controle cidadão.", accent: "bg-[#756590]" },
  saude: { label: "Saúde", description: "Rede, capacidade, produção e indicadores epidemiológicos.", accent: "bg-[#bd5c5c]" },
  "infraestrutura-e-cidades": { label: "Infraestrutura e cidades", description: "Saneamento, energia, frota e serviços urbanos.", accent: "bg-[#4d7180]" },
  "protecao-social": { label: "Proteção social", description: "Benefícios e programas em recorte agregado.", accent: "bg-[#976082]" },
  "seguranca-publica": { label: "Segurança pública", description: "Ocorrências e políticas de segurança em fontes oficiais.", accent: "bg-[#615f66]" },
  "territorio-e-demografia": { label: "Território e demografia", description: "População, limites e características territoriais.", accent: "bg-[#48727a]" },
  transparencia: { label: "Transparência e licitações", description: "Contratações, contratos e execução fiscal.", accent: "bg-[#866e31]" },
};

function sectorCopy(slug: string) {
  return sectorContent[slug] ?? {
    label: slug.replaceAll("-", " ").replace(/^./, (letter) => letter.toLocaleUpperCase("pt-BR")),
    description: "Fontes públicas identificadas para este tema.",
    accent: "bg-teal",
  };
}

export function MunicipalityProfile({ code }: { code: string }) {
  const [data, setData] = useState<MunicipalitySummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<MunicipalitySummary>(`/municipios/${encodeURIComponent(code)}/summary`, controller.signal)
      .then(setData)
      .catch((reason: Error) => reason.name !== "AbortError" && setError(reason.message));
    return () => controller.abort();
  }, [code]);

  const sectors = useMemo(
    () => [...(data?.sectors ?? [])].sort((a, b) => b.published_datasets - a.published_datasets || a.slug.localeCompare(b.slug)),
    [data],
  );

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Carregando perfil municipal…" />;

  const activeSectors = sectors.filter((sector) => sector.published_datasets > 0).length;

  return (
    <div>
      <section className="editorial-hero rounded-[2rem] px-6 py-9 shadow-[0_30px_80px_rgba(6,47,41,0.22)] sm:px-10 sm:py-12 lg:px-14">
        <div className="relative z-10 max-w-4xl">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-white/70">
            <MapPinIcon className="h-4 w-4" /> {data.municipality.state} · código IBGE {data.municipality.ibge_code}
          </p>
          <h1 className="display-title mt-5 text-5xl leading-[0.92] sm:text-7xl lg:text-8xl">{data.municipality.name}</h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-white/75 sm:text-lg">
            Uma leitura pública do município, com dados oficiais, período de referência e origem visíveis em cada indicador.
          </p>
          <div className="mt-9 grid max-w-3xl gap-3 sm:grid-cols-3">
            {[
              [data.catalog_summary.published_datasets, "conjuntos com dados"],
              [activeSectors, "temas disponíveis"],
              [data.catalog_summary.candidate_sources, "fontes mapeadas"],
            ].map(([value, label]) => (
              <div key={label} className="metric-tile rounded-2xl p-4 transition duration-300 hover:-translate-y-1 hover:bg-white/15">
                <p className="text-3xl font-black">{value}</p>
                <p className="mt-1 text-xs text-white/65">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-16" aria-labelledby="sector-title">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow">Explore por tema</p>
            <h2 id="sector-title" className="display-title mt-2 text-4xl sm:text-5xl">O município em camadas</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-ink/60">
              “Dados disponíveis” significa que há registros publicados para este município. Fontes mapeadas ainda podem estar em análise.
            </p>
          </div>
          <Link href="/fontes" className="group inline-flex items-center gap-2 text-sm font-bold text-[#087875]">
            Consultar catálogo nacional <ArrowUpRightIcon className="h-4 w-4 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </Link>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {sectors.map((sector, index) => {
            const content = sectorCopy(sector.slug);
            const published = sector.published_datasets > 0;
            return (
              <Link href={`/municipios/${code}/${sector.slug}`} key={sector.slug} className="card interactive-card group relative overflow-hidden p-6">
                <span className={`absolute inset-y-0 left-0 w-1.5 ${content.accent} transition-all duration-300 group-hover:w-2`} />
                <div className="flex items-start justify-between gap-4">
                  <span className="text-xs font-black tabular-nums text-ink/30">{String(index + 1).padStart(2, "0")}</span>
                  <StatusBadge status={published ? "published" : "discovered"} />
                </div>
                <div className="mt-7 flex items-center gap-3">
                  <span className="rounded-xl bg-ink/[0.045] p-2.5 text-[#073f35] transition duration-300 group-hover:scale-110 group-hover:text-teal"><SectorIcon slug={sector.slug} className="h-6 w-6" /></span>
                  <h3 className="text-xl font-black tracking-tight">{content.label}</h3>
                </div>
                <p className="mt-2 min-h-10 text-sm leading-5 text-ink/55">{content.description}</p>
                <div className="mt-6 flex items-end justify-between gap-3 border-t border-ink/10 pt-5">
                  <div>
                    {published ? <><p className="text-3xl font-black text-[#073f35]">{sector.published_datasets}</p><p className="text-xs text-ink/50">conjunto{sector.published_datasets === 1 ? "" : "s"} publicado{sector.published_datasets === 1 ? "" : "s"}</p></> : <><p className="text-sm font-black text-[#073f35]">Em implantação</p><p className="mt-1 text-xs text-ink/50">sem dado temático publicado</p></>}
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold">{sector.candidate_sources}</p>
                    <p className="text-xs text-ink/45">fontes mapeadas</p>
                  </div>
                  <ArrowUpRightIcon className="h-5 w-5 shrink-0 text-teal transition duration-300 group-hover:-translate-y-1 group-hover:translate-x-1" />
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mt-20" aria-labelledby="available-title">
        <div className="flex items-start gap-3">
          <CheckCircleIcon className="mt-1 h-6 w-6 text-teal" />
          <div>
            <p className="eyebrow">Séries gerais</p>
            <h2 id="available-title" className="display-title mt-2 text-4xl">Indicadores homologados</h2>
          </div>
        </div>
        {data.available_indicators.length ? (
          <div className="mt-7 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {data.available_indicators.map((card) => <DataCard key={card.indicator.code} indicator={card.indicator} observation={card} municipalityCode={code} />)}
          </div>
        ) : (
          <div className="card mt-7 flex gap-4 p-8">
            <CircleStackIcon className="h-7 w-7 shrink-0 text-ink/35" />
            <div>
              <p className="font-bold">Ainda não há observações na coleção geral.</p>
              <p className="mt-2 text-sm text-ink/65">Consulte os temas acima: dados especializados podem estar disponíveis mesmo sem um cartão nesta coleção.</p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
