"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Challenge = { question: string; token: string; expires_in: number };

export function SourceContributionForm() {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  function refreshChallenge() {
    fetch(`${API_BASE}/v1/source-submissions/captcha`, { headers: { Accept: "application/json" } })
      .then((response) => response.json() as Promise<Challenge>)
      .then(setChallenge)
      .catch(() => setError("Não foi possível carregar o desafio de segurança."));
  }
  useEffect(refreshChallenge, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) return;
    const element = event.currentTarget;
    setSending(true); setError(""); setMessage("");
    const form = new FormData(element);
    const payload = {
      public_name: String(form.get("public_name") ?? ""),
      organization: String(form.get("organization") ?? ""),
      url: String(form.get("url") ?? ""),
      description: String(form.get("description") ?? ""),
      contact: String(form.get("contact") ?? "") || null,
      notification_opt_in: form.get("notification_opt_in") === "on",
      captcha_token: challenge.token,
      captcha_answer: String(form.get("captcha_answer") ?? ""),
      website: String(form.get("website") ?? ""),
    };
    const response = await fetch(`${API_BASE}/v1/source-submissions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const body = await response.json().catch(() => ({})) as { detail?: string; id?: string; message?: string };
    if (!response.ok) { setError(body.detail ?? "Não foi possível enviar a sugestão."); refreshChallenge(); setSending(false); return; }
    setMessage(`${body.message} Protocolo: ${body.id}`); element.reset(); refreshChallenge(); setSending(false);
  }

  return <form onSubmit={submit} className="card grid gap-5 p-6 sm:p-8">
    <div className="grid gap-5 md:grid-cols-2"><label className="text-sm font-bold">Nome público<input required name="public_name" minLength={2} maxLength={160} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label><label className="text-sm font-bold">Órgão ou organização<input required name="organization" minLength={2} maxLength={240} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label></div>
    <label className="text-sm font-bold">URL pública da fonte<input required name="url" type="url" pattern="https://.*" placeholder="https://..." className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label>
    <label className="text-sm font-bold">Descrição<textarea required name="description" minLength={20} maxLength={4000} rows={6} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" placeholder="Explique o conteúdo, cobertura, formato e por que a fonte é relevante." /></label>
    <label className="text-sm font-bold">Contato por e-mail <span className="font-normal text-ink/50">(opcional)</span><input name="contact" type="email" maxLength={320} className="mt-2 w-full rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label>
    <label className="flex items-start gap-3 text-sm"><input name="notification_opt_in" type="checkbox" className="mt-1" /><span>Quero receber atualização sobre a triagem. O contato será usado somente para esta finalidade.</span></label>
    <div className="hidden" aria-hidden="true"><label>Website<input name="website" tabIndex={-1} autoComplete="off" /></label></div>
    <label className="text-sm font-bold">Verificação: {challenge?.question ?? "carregando…"}<input required name="captcha_answer" inputMode="numeric" maxLength={10} className="mt-2 block w-40 rounded-xl border border-ink/20 px-4 py-3 font-normal" /></label>
    <p className="text-xs leading-5 text-ink/55">O envio não acessa a URL e não publica dados. A sugestão entra em fila de revisão humana. Leia a <Link href="/privacidade" className="font-bold text-teal underline">política de privacidade</Link>.</p>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-900">{error}</p>}{message && <p role="status" className="rounded-xl bg-mist p-4 text-sm font-bold text-teal">{message}</p>}
    <button disabled={sending || !challenge} className="button-primary w-fit disabled:opacity-50">{sending ? "Enviando…" : "Enviar para triagem"}</button>
  </form>;
}
