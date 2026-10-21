import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchPortal } from "@/components/SearchPortal";
import { LoadingState } from "@/components/LoadingState";

export const metadata: Metadata = { title: "Buscar dados e fontes", description: "Pesquisa territorial e catálogo nacional de fontes públicas candidatas e integradas." };
export default function Page() { return <div className="container-page py-16"><p className="eyebrow">Pesquisa pública</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Buscar territórios e fontes</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Os filtros ficam na URL para que a consulta possa ser copiada. Fonte descoberta, integração e dado publicado são estados diferentes.</p><Suspense fallback={<LoadingState />}><SearchPortal /></Suspense></div>; }
