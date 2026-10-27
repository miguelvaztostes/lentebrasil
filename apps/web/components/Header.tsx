"use client";

import { Bars3Icon, MagnifyingGlassIcon, XMarkIcon } from "@heroicons/react/24/outline";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

const primaryLinks = [
  ["Início", "/"],
  ["Indicadores", "/indicadores"],
  ["Regiões", "/brasil"],
  ["Pesquisa", "/pesquisa"],
  ["Comparar", "/comparar"],
  ["Fontes", "/fontes"],
  ["Dados abertos", "/dados-abertos"],
];

const utilityLinks = [
  ["Sobre", "/sobre"],
  ["Metodologia", "/metodologia"],
  ["API", "/dados-abertos"],
  ["Contribuir", "/contribuir/fonte"],
];

export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-ink/10 bg-[#fbfaf7]/92 shadow-[0_8px_30px_rgba(6,47,41,0.04)] backdrop-blur-xl">
      <div className="bg-[#073f35] text-white">
        <div className="container-page flex h-7 items-center justify-between gap-4 text-[10px] font-bold uppercase tracking-[0.14em] text-white/75">
          <span>Observatório de dados públicos municipais</span>
          <nav aria-label="Navegação institucional" className="hidden items-center gap-5 sm:flex">
            {utilityLinks.map(([label, href]) => <Link key={label} href={href} className="transition hover:text-[#f2ca61]">{label}</Link>)}
          </nav>
        </div>
      </div>
      <div className="container-page flex min-h-[4.75rem] items-center justify-between gap-6">
        <Link href="/" aria-label="Lente Brasil — página inicial" className="group flex shrink-0 items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-[#073f35] transition duration-300 group-hover:rotate-6 group-hover:scale-105">
            <Image src="/lente-brasil-simbolo.svg" alt="" width={34} height={34} priority />
          </span>
          <span className="display-title text-2xl leading-none text-[#073f35]">Lente <em>Brasil</em></span>
        </Link>
        <nav aria-label="Navegação principal" className="hidden min-w-0 items-center gap-5 xl:flex">
          {primaryLinks.map(([label, href]) => (
            <Link key={href} href={href} className="relative whitespace-nowrap py-2 text-[13px] font-semibold text-ink/70 transition after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:origin-left after:scale-x-0 after:bg-gold after:transition-transform hover:text-[#073f35] hover:after:scale-x-100">
              {label}
              {label === "Pesquisa" && <span className="absolute -right-4 -top-1 text-[7px] font-black uppercase tracking-wide text-[#9a6e11]">novo</span>}
            </Link>
          ))}
          <Link href="/buscar" aria-label="Buscar no Lente Brasil" className="ml-1 grid h-10 w-10 place-items-center rounded-full border border-ink/15 transition hover:-translate-y-0.5 hover:border-teal hover:bg-teal/10 hover:text-teal">
            <MagnifyingGlassIcon className="h-4 w-4" />
          </Link>
        </nav>
        <button type="button" className="rounded-full border border-ink/10 p-2.5 transition hover:border-teal hover:text-teal xl:hidden" aria-label={open ? "Fechar menu" : "Abrir menu"} aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? <XMarkIcon className="h-6 w-6" /> : <Bars3Icon className="h-6 w-6" />}
        </button>
      </div>
      {open && (
        <nav aria-label="Navegação móvel" className="container-page grid grid-cols-2 gap-2 border-t border-ink/10 py-4 xl:hidden">
          {[...primaryLinks, ...utilityLinks].map(([label, href]) => (
            <Link key={`${label}-${href}`} href={href} onClick={() => setOpen(false)} className="rounded-xl px-3 py-3 text-sm font-semibold transition hover:bg-teal/10 hover:text-teal">{label}</Link>
          ))}
          <Link href="/buscar" onClick={() => setOpen(false)} className="col-span-2 mt-1 flex items-center justify-center gap-2 rounded-xl bg-[#073f35] px-4 py-3 text-sm font-bold text-white"><MagnifyingGlassIcon className="h-4 w-4" /> Buscar dados</Link>
        </nav>
      )}
    </header>
  );
}
