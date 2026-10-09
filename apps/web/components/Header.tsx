"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { Bars3Icon, XMarkIcon } from "@heroicons/react/24/outline";

const links = [
  ["Indicadores", "/indicadores"],
  ["Transparência", "/transparencia"],
  ["Educação", "/educacao"],
  ["Saúde", "/saude"],
  ["Fontes", "/fontes"],
  ["Dados abertos", "/dados-abertos"],
];

export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-ink/10 bg-[#fbfaf7]/95 backdrop-blur">
      <div className="container-page flex h-20 items-center justify-between gap-6">
        <Link href="/" aria-label="Lente Ribeirão — página inicial">
          <Image src="/lente-ribeirao-logo.svg" alt="Lente Ribeirão" width={188} height={48} priority />
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

