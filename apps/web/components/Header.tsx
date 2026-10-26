"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { Bars3Icon, XMarkIcon } from "@heroicons/react/24/outline";

const links = [
  ["Brasil", "/brasil"],
  ["Pesquisa", "/pesquisa"],
  ["Comparar", "/comparar"],
  ["Catálogo", "/buscar"],
  ["Contribuir", "/contribuir/fonte"],
  ["Fontes", "/fontes"],
  ["Lente Ribeirão", "/municipios/3543402"],
  ["Dados abertos", "/dados-abertos"],
];

export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-ink/10 bg-[#fbfaf7]/95 backdrop-blur">
      <div className="container-page flex h-20 items-center justify-between gap-6">
        <Link href="/" aria-label="Lente Brasil — página inicial" className="flex items-center gap-3">
          <Image src="/lente-ribeirao-simbolo.svg" alt="" width={42} height={42} priority />
          <span className="text-xl font-black tracking-tight">Lente Brasil</span>
        </Link>
        <nav aria-label="Navegação principal" className="hidden items-center gap-6 lg:flex">
          {links.map(([label, href]) => (
            <Link key={href} href={href} className="text-sm font-semibold text-ink/75 hover:text-teal">
              {label}
            </Link>
          ))}
        </nav>
        <button
          type="button"
          className="rounded-lg p-2 lg:hidden"
          aria-label={open ? "Fechar menu" : "Abrir menu"}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <XMarkIcon className="h-6 w-6" /> : <Bars3Icon className="h-6 w-6" />}
        </button>
      </div>
      {open && (
        <nav aria-label="Navegação móvel" className="container-page grid gap-1 border-t border-ink/10 py-4 lg:hidden">
          {links.map(([label, href]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)} className="rounded-lg px-3 py-3 font-semibold hover:bg-teal/10">
              {label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

