import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StateDirectory } from "@/components/StateDirectory";

const states = new Set(["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]);
export async function generateMetadata({ params }: { params: Promise<{ uf: string }> }): Promise<Metadata> { const { uf } = await params; return { title: `Municípios de ${uf.toUpperCase()}` }; }
export default async function Page({ params }: { params: Promise<{ uf: string }> }) { const { uf: raw } = await params; const uf = raw.toUpperCase(); if (!states.has(uf)) notFound(); return <div className="container-page py-16"><p className="eyebrow">Diretório territorial</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Municípios de {uf}</h1><p className="mb-10 mt-5 max-w-3xl text-lg leading-8 text-ink/65">Selecione um município para abrir seu perfil. Estar no diretório não implica possuir observações publicadas.</p><StateDirectory uf={uf} /></div>; }
