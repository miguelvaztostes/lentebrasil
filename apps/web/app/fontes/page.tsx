import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchPortal } from "@/components/SearchPortal";
import { LoadingState } from "@/components/LoadingState";

export const metadata: Metadata = { title: "Catálogo nacional de fontes", description: "Inventário nacional com estado de descoberta, integração, licença, cobertura e publicação." };
export default function Page() { return <div className="container-page py-16"><p className="eyebrow">Rastreabilidade nacional</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Fontes públicas catalogadas</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">O inventário registra candidatos sem afirmar que todos foram verificados ou integrados. Cada item expõe seu estado e liga ao endereço oficial indicado.</p><Suspense fallback={<LoadingState />}><SearchPortal /></Suspense></div>; }
