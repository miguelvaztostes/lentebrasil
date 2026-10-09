import type { Metadata } from "next";

export const metadata: Metadata = { title: "Metodologia" };
const steps = [
  ["1", "Descobrir", "Confirmamos endpoint, formato, município, licença conhecida e frequência antes da primeira carga."],
  ["2", "Preservar", "Guardamos o bruto quando adequado; quando o arquivo contém contatos, como no CNES, guardamos somente hash, URL e agregados."],
  ["3", "Validar", "Schema, unidade, domínio geográfico, duplicidade e faixas são verificados antes de publicar."],
  ["4", "Versionar", "Mudanças reais criam revisão. Repetições idênticas não duplicam observações."],
];
export default function Page() {
  return <div className="container-page py-16"><p className="eyebrow">Como trabalhamos</p><h1 className="mt-3 text-4xl font-black tracking-tight sm:text-6xl">Metodologia</h1><p className="mt-5 max-w-3xl text-lg leading-8 text-ink/65">Um número só entra no observatório quando conseguimos explicar o que mede, de onde veio e em que período vale.</p><div className="mt-12 grid gap-5 md:grid-cols-2">{steps.map(([n, title, text]) => <section key={n} className="card p-7"><span className="text-4xl font-black text-teal/30">{n}</span><h2 className="mt-4 text-xl font-extrabold">{title}</h2><p className="mt-3 text-sm leading-6 text-ink/65">{text}</p></section>)}</div><section className="mt-12 rounded-2xl bg-ink p-8 text-white"><h2 className="text-2xl font-extrabold">Regras de leitura</h2><ul className="mt-5 grid gap-3 text-sm leading-6 text-white/70 md:grid-cols-2"><li>• Zero não significa dado ausente.</li><li>• Empenho, liquidação e pagamento não são somados.</li><li>• Cadastro CNES não mede qualidade de atendimento.</li><li>• Estimativa populacional não é Censo.</li><li>• Revisões da fonte permanecem auditáveis.</li><li>• Comparações incompatíveis são bloqueadas.</li></ul></section></div>;
}

