import type { Metadata } from "next";
import { MunicipalitySector } from "@/components/MunicipalitySector";

export async function generateMetadata({ params }: { params: Promise<{ ibgeCode: string; setor: string }> }): Promise<Metadata> { const { ibgeCode, setor } = await params; return { title: `${setor.replaceAll("-", " ")} · ${ibgeCode}` }; }
export default async function Page({ params }: { params: Promise<{ ibgeCode: string; setor: string }> }) { const { ibgeCode, setor } = await params; return <div className="container-page py-16"><MunicipalitySector code={ibgeCode} sector={setor} /></div>; }
