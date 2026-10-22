import type { Metadata } from "next";
import { SchoolDetail } from "@/components/SchoolDetail";

export async function generateMetadata({ params }: { params: Promise<{ inepCode: string }> }): Promise<Metadata> { const { inepCode } = await params; return { title: `Escola ${inepCode}` }; }
export default async function Page({ params }: { params: Promise<{ inepCode: string }> }) { const { inepCode } = await params; return <div className="container-page py-16"><SchoolDetail code={inepCode} /></div>; }
