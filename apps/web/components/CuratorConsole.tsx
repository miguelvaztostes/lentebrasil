"use client";

import { FormEvent, useState } from "react";
import { API_BASE } from "@/lib/api";

type Submission = {
  id: string;
  public_name: string;
  organization: string;
  url: string;
  description: string;
  status: string;
  created_at: string;
  has_contact: boolean;
};

export function CuratorConsole() {
  const [token, setToken] = useState("");
  const [items, setItems] = useState<Submission[]>([]);
  const [error, setError] = useState("");

  async function loadQueue() {
    setError("");
    const response = await fetch(`${API_BASE}/v1/curation/submissions`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      cache: "no-store",
    });
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
      items?: Submission[];
    };
    if (!response.ok) {
      setError(body.detail ?? "Acesso negado");
      return;
    }
    setItems(body.items ?? []);
  }

  async function load(event: FormEvent) {
    event.preventDefault();
    await loadQueue();
  }

  async function review(id: string, toStatus: string) {
    const reason = window.prompt("Justificativa auditável (mínimo 12 caracteres):");
    if (!reason) return;
    const response = await fetch(`${API_BASE}/v1/curation/submissions/${id}/reviews`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ to_status: toStatus, reason, evidence: {} }),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: string };
      setError(body.detail ?? "Transição recusada");
      return;
    }
    await loadQueue();
  }

  return (
    <div className="grid gap-6">
      <form onSubmit={load} className="card p-6">
        <label className="text-sm font-bold">
          Token OIDC de sessão com MFA
          <input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal"
          />
        </label>
        <p className="mt-2 text-xs text-ink/55">
          O token permanece somente na memória desta aba e não é gravado no navegador.
        </p>
        <button className="button-primary mt-4">Abrir fila</button>
      </form>
      {error && (
        <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-900">
          {error}
        </p>
      )}
      <div className="grid gap-4">
        {items.map((item) => (
          <article key={item.id} className="card p-6">
            <p className="eyebrow">{item.status} · {item.organization}</p>
            <h2 className="mt-2 text-xl font-extrabold">{item.public_name}</h2>
            <p className="mt-3 text-sm text-ink/65">{item.description}</p>
            <p className="mt-3 break-all rounded-lg bg-mist p-3 text-sm text-ink/70">
              URL não verificada: {item.url}
            </p>
            <p className="mt-2 text-xs text-ink/55">
              Copie a URL somente para o ambiente segregado de validação. A fila não a acessa.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {item.status === "received" && <button type="button" onClick={() => review(item.id, "triage")} className="button-secondary">Iniciar triagem</button>}
              {item.status === "triage" && <button type="button" onClick={() => review(item.id, "verified")} className="button-secondary">Marcar metadado verificado</button>}
              {item.status === "verified" && <button type="button" onClick={() => review(item.id, "approved")} className="button-secondary">Aprovar sugestão</button>}
              {item.status === "approved" && <button type="button" onClick={() => review(item.id, "published")} className="button-secondary">Publicar registro da sugestão</button>}
              {item.status !== "published" && <button type="button" onClick={() => review(item.id, "rejected")} className="button-secondary">Rejeitar</button>}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
