"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { getRun, reportUrl } from "@/lib/api";
import type { RunSnapshot, StakeholderProfile } from "@/lib/types";
import { ROLE_LABEL_PT, SENTIMENT_LABEL_PT } from "@/lib/types";

const ARCHETYPE_NOTE: Record<string, string> = {};

function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const s = await getRun(id);
        if (cancelled) return;
        setSnap(s);
        if (s.status !== "running" && timer.current) {
          clearInterval(timer.current);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    }
    poll();
    timer.current = setInterval(poll, 1500);
    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
    };
  }, [id]);

  if (err) {
    return (
      <div className="page" style={{ paddingTop: 68 }}>
        <div className="flag">
          <p>{err}</p>
        </div>
      </div>
    );
  }

  if (!snap || snap.status === "running") {
    return (
      <div className="page" style={{ paddingTop: 68 }}>
        <p className="eyebrow">Sales Digital Twins</p>
        <h1 className="display" style={{ marginBottom: 24 }}>
          O comitê está <span className="voice">deliberando.</span>
        </h1>
        <div className="ledger" style={{ maxWidth: 480 }}>
          <div className="ledger-head">
            <span className="live">Rodando</span>
            <span className="meta">run {id.slice(0, 8)}</span>
          </div>
          <div className="figs">
            {(snap?.log ?? []).slice(-6).map((ev, i) => (
              <div className="fig" key={i}>
                <span>
                  {ev.event === "start" ? "▸" : "✓"} {ev.agent}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (snap.status === "error") {
    return (
      <div className="page" style={{ paddingTop: 68 }}>
        <p className="eyebrow">Sales Digital Twins</p>
        <h1 className="display" style={{ marginBottom: 24 }}>
          A simulação falhou.
        </h1>
        <div className="flag" style={{ maxWidth: 640 }}>
          <span className="flag-k">Erro</span>
          <p>{snap.error}</p>
        </div>
      </div>
    );
  }

  const result = snap.result!;
  const { account, personas, transcript, verdict } = result;

  const realPersonas = personas.filter((p) => p.source === "real" && p.role !== "salesman");
  const archetypePersonas = personas.filter((p) => p.source === "archetype" && p.role !== "salesman");
  const committee = personas.filter((p) => p.role !== "salesman");
  const realPct = committee.length > 0 ? (realPersonas.length / committee.length) * 100 : 0;

  return (
    <div className="page" style={{ paddingTop: 68, paddingBottom: 90 }}>
      <p className="eyebrow">Sales Digital Twins — {account.account_name}</p>

      <div className="hero" style={{ marginBottom: 56 }}>
        <div>
          <h1 className="display" style={{ marginBottom: 18 }}>
            O comitê reagiu.{" "}
            <span className="voice">Agora a leitura é sua.</span>
          </h1>
          <p className="lede">{account.pitch_summary}</p>
          <p className="body-text" style={{ marginTop: 14 }}>
            {account.proposed_solution}
          </p>
        </div>

        <div className="ledger">
          <div className="ledger-head">
            <span className="live">Concluído</span>
            <span className="meta">{fmtDuration(result.duration_seconds)}</span>
          </div>

          <div className="bar-row">
            <div className="bar-label">
              <span>Comitê simulado</span>
              <b>{committee.length}</b>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: "100%", background: "var(--clay)" }} />
            </div>
            <div className="bar-label">
              <span>Grounded em dados reais</span>
              <b>{realPersonas.length}</b>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${realPct}%`, background: "var(--ledger-mint)" }} />
            </div>
          </div>

          <div className="figs">
            <div className="fig">
              <b>{result.llm_calls}</b>
              <span>chamadas LLM</span>
            </div>
            <div className="fig">
              <b>{transcript.length}</b>
              <span>falas no debate</span>
            </div>
            <div className="fig">
              <b>{Math.max(...transcript.map((t) => t.round_number), 0)}</b>
              <span>rounds</span>
            </div>
          </div>

          <div className="figs" style={{ borderTop: "1px solid var(--ledger-rule)" }}>
            <div className="fig" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
              <span>modelo persona</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ledger-ink)" }}>
                {result.model_persona}
              </span>
            </div>
            <div className="fig" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
              <span>modelo síntese</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ledger-ink)" }}>
                {result.model_synthesizer}
              </span>
            </div>
          </div>
        </div>
      </div>

      {realPersonas.length > 0 && (
        <div className="measured on-paper" style={{ marginBottom: 24 }}>
          <span className="tick">✓</span>
          <p>
            <span className="k">Grounded em dados reais</span>
            {realPersonas
              .map((p) => `${p.name} (${ROLE_LABEL_PT[p.role]})`)
              .join(", ")}{" "}
            {realPersonas.length === 1 ? "tem falas apoiadas" : "têm falas apoiadas"} em fatos
            verificáveis coletados sobre a pessoa real — veja{" "}
            <code>grounding_facts</code> de cada perfil abaixo para conferir a fonte.
          </p>
        </div>
      )}

      {archetypePersonas.length > 0 && (
        <div className="flag" style={{ marginBottom: 56 }}>
          <span className="flag-k">Sem dado real</span>
          <p>
            {archetypePersonas
              .map((p) => `${p.name} (${ROLE_LABEL_PT[p.role]})`)
              .join(", ")}{" "}
            {archetypePersonas.length === 1 ? "não tem" : "não têm"} nenhum fato real
            associado — {archetypePersonas.length === 1 ? "sua fala" : "suas falas"} vem de um arquétipo
            genérico do papel. Trate {archetypePersonas.length === 1 ? "a reação dela" : "as reações delas"} como
            ilustrativa, não preditiva.
          </p>
        </div>
      )}

      <div className="section">
        <p className="eyebrow">Comitê</p>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Papel</th>
                <th>Nome</th>
                <th>Fonte</th>
                <th className="num">Peso de decisão</th>
                <th>Prioridades</th>
              </tr>
            </thead>
            <tbody>
              {personas.map((p: StakeholderProfile) => (
                <tr key={p.role}>
                  <td>{ROLE_LABEL_PT[p.role]}</td>
                  <td>{p.name}</td>
                  <td>
                    {p.source === "real" ? (
                      <span className="pill" style={{ borderColor: "var(--mint)", color: "var(--mint)" }}>
                        real
                      </span>
                    ) : (
                      <span className="pill" style={{ borderColor: "var(--clay)", color: "var(--clay)" }}>
                        arquétipo
                      </span>
                    )}
                  </td>
                  <td className="num">{p.decision_power.toFixed(2)}</td>
                  <td className="body-text" style={{ margin: 0 }}>
                    {p.priorities.slice(0, 3).join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section">
        <p className="eyebrow">Transcrição do debate</p>
        <div className="stack">
          {transcript.map((t, i) => (
            <div key={i} className="card">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
                <span className="h3" style={{ margin: 0 }}>
                  {t.name} · {ROLE_LABEL_PT[t.role]}
                </span>
                <span className="mono" style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                  round {t.round_number} · {SENTIMENT_LABEL_PT[t.sentiment]}
                </span>
              </div>
              <p className="body-text" style={{ maxWidth: "none" }}>{t.statement}</p>
              {t.objections_raised.length > 0 && (
                <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>
                  {t.objections_raised.map((o, j) => (
                    <li key={j} className="body-text" style={{ maxWidth: "none" }}>
                      {o}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>

      {verdict && (
        <div className="section">
          <p className="eyebrow">Veredito</p>
          <p className="lede" style={{ marginBottom: 24 }}>
            {verdict.consensus_reached ? (
              <>O comitê chegou a um <span className="voice">consenso.</span></>
            ) : (
              <>O comitê <span className="voice">não chegou a um consenso.</span></>
            )}
          </p>
          <p className="body-text" style={{ marginBottom: 24 }}>{verdict.risk_summary}</p>

          {verdict.blocking_stakeholders.length > 0 && (
            <div className="flag" style={{ marginBottom: 24, maxWidth: 640 }}>
              <span className="flag-k">Bloqueadores</span>
              <p>{verdict.blocking_stakeholders.map((r) => ROLE_LABEL_PT[r]).join(", ")}</p>
            </div>
          )}

          <div className="tbl-wrap" style={{ marginBottom: 24 }}>
            <table>
              <thead>
                <tr>
                  <th>MEDDPICC</th>
                  <th>Avaliação</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(verdict.meddpicc_scorecard).map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ textTransform: "capitalize" }}>{k}</td>
                    <td className="body-text" style={{ margin: 0 }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {verdict.seller_coaching && (
            <div className="card" style={{ marginBottom: 24 }}>
              <p className="h3">
                Coach — nota: <span className="mono">{verdict.seller_coaching.pitch_grade}</span>
              </p>
              <p className="body-text" style={{ maxWidth: "none" }}>
                <strong>O que funcionou:</strong>{" "}
                {verdict.seller_coaching.what_landed.join(" · ")}
              </p>
              <p className="body-text" style={{ maxWidth: "none" }}>
                <strong>O que pegou mal:</strong>{" "}
                {verdict.seller_coaching.what_backfired.join(" · ")}
              </p>
              <p className="body-text" style={{ maxWidth: "none", marginBottom: 0 }}>
                <strong>Reescreva assim:</strong>{" "}
                {verdict.seller_coaching.rewrite_suggestions.join(" · ")}
              </p>
            </div>
          )}
        </div>
      )}

      <div className="section">
        <p className="eyebrow">Exportar</p>
        <div className="row gap-12">
          <a className="btn secondary" href={reportUrl(id, "html")} target="_blank" rel="noreferrer">
            Relatório HTML
          </a>
          <a className="btn secondary" href={reportUrl(id, "md")} target="_blank" rel="noreferrer">
            Relatório Markdown
          </a>
        </div>
      </div>
    </div>
  );
}
