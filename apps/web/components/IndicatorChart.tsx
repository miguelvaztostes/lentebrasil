"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Observation } from "@/lib/api";

export function IndicatorChart({ items, unit }: { items: Observation[]; unit: string }) {
  const data = items
    .filter((item) => item.value !== null)
    .map((item) => ({ year: new Date(item.period_end).getUTCFullYear(), value: Number(item.value) }));
  if (data.length < 2) {
    return <p className="rounded-xl bg-paper p-5 text-sm text-ink/65">O gráfico aparece quando há pelo menos dois períodos comparáveis.</p>;
  }
  const formatter = (value: number) => unit === "BRL nominal"
    ? new Intl.NumberFormat("pt-BR", { notation: "compact", style: "currency", currency: "BRL" }).format(value)
    : new Intl.NumberFormat("pt-BR", { notation: "compact" }).format(value);
  return (
    <div role="img" aria-label={`Gráfico de linha com ${data.length} períodos. A tabela acessível está logo abaixo.`} className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 20, right: 20, left: 12, bottom: 8 }}>
          <CartesianGrid stroke="#dfe7e7" strokeDasharray="4 4" />
          <XAxis dataKey="year" stroke="#52636f" tickLine={false} />
          <YAxis stroke="#52636f" tickLine={false} width={74} tickFormatter={formatter} />
          <Tooltip formatter={(value) => [formatter(Number(value)), unit]} labelFormatter={(label) => `Ano ${label}`} />
          <Line type="monotone" dataKey="value" stroke="#119E9C" strokeWidth={4} dot={{ fill: "#E3AF42", stroke: "#102333", strokeWidth: 2, r: 5 }} activeDot={{ r: 7 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

