export function LoadingState({ label = "Carregando dados oficiais…" }: { label?: string }) {
  return (
    <div role="status" className="card flex min-h-40 items-center justify-center p-8 text-sm text-ink/60">
      <span className="mr-3 h-4 w-4 animate-pulse rounded-full bg-teal" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm leading-6 text-red-900">
      <strong>Os dados não puderam ser carregados agora.</strong> {message} Nenhum valor alternativo foi estimado.
    </div>
  );
}

