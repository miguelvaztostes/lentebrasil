const styles: Record<string, string> = {
  confirmed: "bg-teal/10 text-[#087875]",
  success: "bg-teal/10 text-[#087875]",
  available: "bg-teal/10 text-[#087875]",
  pending: "bg-gold/20 text-[#76540e]",
  requires_manual_import: "bg-gold/20 text-[#76540e]",
  stale: "bg-orange-100 text-orange-800",
  failed: "bg-red-100 text-red-800",
  unavailable: "bg-slate-100 text-slate-700",
  discovered: "bg-sky-100 text-sky-800",
  pending_review: "bg-gold/20 text-[#76540e]",
  integrated: "bg-indigo-100 text-indigo-800",
  published: "bg-teal/10 text-[#087875]",
  restricted: "bg-purple-100 text-purple-800",
  not_published: "bg-slate-100 text-slate-700",
};

const labels: Record<string, string> = {
  confirmed: "confirmada",
  success: "atualizada",
  available: "disponível",
  pending: "em verificação",
  requires_manual_import: "importação supervisionada",
  stale: "desatualizada",
  failed: "falha na última coleta",
  unavailable: "indisponível",
  discovered: "descoberta",
  pending_review: "em revisão",
  integrated: "integrada",
  published: "dados publicados",
  restricted: "restrita",
  not_published: "sem dados publicados",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ${styles[status] ?? styles.pending}`}>
      {labels[status] ?? status}
    </span>
  );
}

