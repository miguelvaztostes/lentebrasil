import type { Metadata } from "next";
import { MunicipalityProfile } from "@/components/MunicipalityProfile";

export async function generateMetadata({ params }: { params: Promise<{ ibgeCode: string }> }): Promise<Metadata> { const { ibgeCode } = await params; return { title: `Município ${ibgeCode}`, description: `Perfil municipal, fontes e dados publicados para o código IBGE ${ibgeCode}.` }; }
export default async function Page({ params }: { params: Promise<{ ibgeCode: string }> }) { const { ibgeCode } = await params; return <div className="container-page py-16"><MunicipalityProfile code={ibgeCode} /></div>; }
