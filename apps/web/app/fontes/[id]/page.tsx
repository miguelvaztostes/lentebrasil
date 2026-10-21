import type { Metadata } from "next";
import { SourceDetail } from "@/components/SourceDetail";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> { const { id } = await params; return { title: `Fonte ${id}` }; }
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <div className="container-page py-16"><SourceDetail id={id} /></div>; }
