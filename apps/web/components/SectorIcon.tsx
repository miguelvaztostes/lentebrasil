import {
  AcademicCapIcon,
  BanknotesIcon,
  BeakerIcon,
  BriefcaseIcon,
  BuildingLibraryIcon,
  BuildingOffice2Icon,
  ChartBarIcon,
  CircleStackIcon,
  CloudIcon,
  GlobeAmericasIcon,
  HeartIcon,
  HomeModernIcon,
  MapIcon,
  MusicalNoteIcon,
  ScaleIcon,
  ShieldCheckIcon,
  UserGroupIcon,
} from "@heroicons/react/24/outline";

const icons: Record<string, typeof ChartBarIcon> = {
  "agropecuaria-e-rural": GlobeAmericasIcon,
  "catalogos-e-descoberta": CircleStackIcon,
  "ciencia-e-inovacao": BeakerIcon,
  "cultura-e-turismo": MusicalNoteIcon,
  desenvolvimento: ChartBarIcon,
  "economia-e-trabalho": BriefcaseIcon,
  educacao: AcademicCapIcon,
  "financas-publicas": BanknotesIcon,
  "gestao-publica": BuildingOffice2Icon,
  "infraestrutura-e-cidades": HomeModernIcon,
  "meio-ambiente-e-riscos": CloudIcon,
  "municipal-ribeirao-preto": MapIcon,
  "participacao-e-democracia": UserGroupIcon,
  "protecao-social": HeartIcon,
  saude: HeartIcon,
  "seguranca-publica": ShieldCheckIcon,
  "territorio-e-demografia": MapIcon,
  transparencia: ScaleIcon,
};

export function SectorIcon({ slug, className = "h-8 w-8" }: { slug: string; className?: string }) {
  const Icon = icons[slug] ?? BuildingLibraryIcon;
  return <Icon className={className} aria-hidden="true" />;
}
