"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { getRun, reportUrl } from "@/lib/api";
import type { RunEvent, RunPhase, RunSnapshot, StakeholderProfile, StakeholderRole } from "@/lib/types";
import { ROLE_LABEL, SENTIMENT_LABEL } from "@/lib/types";
import { SPINNER_VERBS } from "@/lib/spinnerVerbs";

function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function useSpinnerVerb(active: boolean, intervalMs = 1700): string {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setI((n) => (n + 1) % SPINNER_VERBS.length), intervalMs);
    return () => clearInterval(t);
  }, [active, intervalMs]);
  return SPINNER_VERBS[i];
}

const PHASE_LABEL: Record<RunPhase, string> = {
  ordering: "Setting the order",
  speaking: "Debating",
  evaluating: "Weighing the round",
  synthesizing: "Drafting the verdict",
};

const DECISION_LINE: Record<NonNullable<RunEvent["decision"]>, string> = {
  continue: "more ground to cover — the debate continues",
  escalate: "escalating — the biggest veto in the room gets the final word",
  conclude: "calling it — moving to the verdict",
};

function roleLabel(agent: string): string {
  return ROLE_LABEL[agent as StakeholderRole] ?? agent;
}

/** One completed narrative beat, for a "done" event. */
function narrate(ev: RunEvent): string {
  if (ev.phase === "ordering") {
    return `Round ${ev.round} begins — the facilitator sets the speaking order.`;
  }
  if (ev.phase === "speaking") {
    const sentiment = ev.sentiment ? ` (${SENTIMENT_LABEL[ev.sentiment]})` : "";
    const objections =
      ev.objections && ev.objections > 0
        ? ` · raised ${ev.objections} objection${ev.objections > 1 ? "s" : ""}`
        : "";
    return `${roleLabel(ev.agent)}${sentiment}: "${ev.preview ?? ""}"${objections}`;
  }
  if (ev.phase === "evaluating") {
    const verdict = ev.decision ? DECISION_LINE[ev.decision] : "weighing the room";
    const reasoning = ev.reasoning ? ` — "${ev.reasoning}"` : "";
    return `Facilitator: ${verdict}${reasoning}`;
  }
  return "The synthesizer has the full transcript — drafting the verdict.";
}

/** The single in-progress line for whichever "start" event hasn't resolved yet. */
function narrateInProgress(ev: RunEvent): string {
  if (ev.phase === "ordering") return `Round ${ev.round}: the facilitator is setting the order…`;
  if (ev.phase === "speaking") return `${roleLabel(ev.agent)} is taking the floor…`;
  if (ev.phase === "evaluating") return "The facilitator is weighing the room's reaction…";
  return "The synthesizer is drafting the verdict…";
}

/** Turn-by-turn story of the debate, auto-scrolling as new beats land. */
function NarrativeFeed({ beats, inProgress }: { beats: RunEvent[]; inProgress: RunEvent | null }) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [beats.length, inProgress?.agent, inProgress?.event]);

  return (
    <div className="narrative" ref={scrollRef}>
      {beats.map((ev, i) => (
        <div className="narrative-line animate-in" key={i}>
          <span className="tag">R{ev.round}</span>
          <p>{narrate(ev)}</p>
        </div>
      ))}
      {inProgress && (
        <div className="narrative-line current">
          <span className="tag">R{inProgress.round}</span>
          <p>{narrateInProgress(inProgress)}</p>
        </div>
      )}
    </div>
  );
}

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const verb = useSpinnerVerb(!err && (!snap || snap.status === "running"));

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
    const log = snap?.log ?? [];
    const last = log[log.length - 1];
    const inProgress = last?.event === "start" ? last : null;
    const beats = log.filter((ev) => ev.event === "done");
    const round = last?.round ?? 1;
    const maxRounds = snap?.max_rounds || undefined;
    const progressPct = Math.round((last?.progress ?? 0) * 100);
    const phaseLabel = last ? PHASE_LABEL[last.phase] : "Getting started";

    return (
      <div className="page animate-in" style={{ paddingTop: 68 }}>
        <p className="eyebrow">Sales Digital Twins</p>
        <h1 className="display" style={{ marginBottom: 24 }}>
          The committee is{" "}
          <span className="voice spinner-verb" key={verb}>
            {verb}
          </span>
          .
        </h1>
        <div className="ledger" style={{ maxWidth: 560 }}>
          <div className="ledger-head">
            <span className="live">Running</span>
            <span className="meta">
              Round {round}
              {maxRounds ? ` of ${maxRounds}` : ""} · {phaseLabel}
            </span>
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${progressPct}%`, background: "var(--ledger-mint)", transition: "width .6s ease" }}
            />
          </div>
          <div className="bar-label" style={{ paddingTop: 0 }}>
            <span>run {id.slice(0, 8)}</span>
            <span>{progressPct}%</span>
          </div>
          <NarrativeFeed beats={beats} inProgress={inProgress} />
        </div>
      </div>
    );
  }

  if (snap.status === "error") {
    return (
      <div className="page animate-in" style={{ paddingTop: 68 }}>
        <p className="eyebrow">Sales Digital Twins</p>
        <h1 className="display" style={{ marginBottom: 24 }}>
          The simulation failed.
        </h1>
        <div className="flag animate-in" style={{ maxWidth: 640, animationDelay: "80ms" }}>
          <span className="flag-k">Error</span>
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
    <div className="page animate-in" style={{ paddingTop: 68, paddingBottom: 90 }}>
      <p className="eyebrow">Sales Digital Twins — {account.account_name}</p>

      <div className="hero" style={{ marginBottom: 56 }}>
        <div className="animate-in">
          <h1 className="display" style={{ marginBottom: 18 }}>
            The committee reacted.{" "}
            <span className="voice">Now the read is yours.</span>
          </h1>
          <p className="lede">{account.pitch_summary}</p>
          <p className="body-text" style={{ marginTop: 14 }}>
            {account.proposed_solution}
          </p>
        </div>

        <div className="ledger animate-in" style={{ animationDelay: "80ms" }}>
          <div className="ledger-head">
            <span className="live">Completed</span>
            <span className="meta">{fmtDuration(result.duration_seconds)}</span>
          </div>

          <div className="bar-row">
            <div className="bar-label">
              <span>Simulated committee</span>
              <b>{committee.length}</b>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: "100%", background: "var(--clay)" }} />
            </div>
            <div className="bar-label">
              <span>Grounded in real data</span>
              <b>{realPersonas.length}</b>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${realPct}%`, background: "var(--ledger-mint)" }} />
            </div>
          </div>

          <div className="figs">
            <div className="fig">
              <b>{result.llm_calls}</b>
              <span>LLM calls</span>
            </div>
            <div className="fig">
              <b>{transcript.length}</b>
              <span>debate turns</span>
            </div>
            <div className="fig">
              <b>{Math.max(...transcript.map((t) => t.round_number), 0)}</b>
              <span>rounds</span>
            </div>
          </div>

          <div className="figs" style={{ borderTop: "1px solid var(--ledger-rule)" }}>
            <div className="fig" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
              <span>persona model</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ledger-ink)" }}>
                {result.model_persona}
              </span>
            </div>
            <div className="fig" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
              <span>synthesizer model</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ledger-ink)" }}>
                {result.model_synthesizer}
              </span>
            </div>
          </div>
        </div>
      </div>

      {realPersonas.length > 0 && (
        <div className="measured on-paper animate-in" style={{ marginBottom: 24, animationDelay: "140ms" }}>
          <span className="tick">✓</span>
          <p>
            <span className="k">Grounded in real data</span>
            {realPersonas
              .map((p) => `${p.name} (${ROLE_LABEL[p.role]})`)
              .join(", ")}{" "}
            {realPersonas.length === 1 ? "has statements backed" : "have statements backed"} by verifiable
            facts collected about the real person — see{" "}
            <code>grounding_facts</code> on each profile below to check the source.
          </p>
        </div>
      )}

      {archetypePersonas.length > 0 && (
        <div className="flag animate-in" style={{ marginBottom: 56, animationDelay: "190ms" }}>
          <span className="flag-k">No real data</span>
          <p>
            {archetypePersonas
              .map((p) => `${p.name} (${ROLE_LABEL[p.role]})`)
              .join(", ")}{" "}
            {archetypePersonas.length === 1 ? "has" : "have"} no real fact
            attached — {archetypePersonas.length === 1 ? "their statement comes" : "their statements come"} from a
            generic role archetype. Treat {archetypePersonas.length === 1 ? "their reaction" : "their reactions"} as
            illustrative, not predictive.
          </p>
        </div>
      )}

      <div className="section">
        <p className="eyebrow">Committee</p>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Role</th>
                <th>Name</th>
                <th>Source</th>
                <th className="num">Decision weight</th>
                <th>Priorities</th>
              </tr>
            </thead>
            <tbody>
              {personas.map((p: StakeholderProfile) => (
                <tr key={p.role}>
                  <td>{ROLE_LABEL[p.role]}</td>
                  <td>{p.name}</td>
                  <td>
                    {p.source === "real" ? (
                      <span className="pill" style={{ borderColor: "var(--mint)", color: "var(--mint)" }}>
                        real
                      </span>
                    ) : (
                      <span className="pill" style={{ borderColor: "var(--clay)", color: "var(--clay)" }}>
                        archetype
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
        <p className="eyebrow">Debate transcript</p>
        <div className="stack">
          {transcript.map((t, i) => (
            <div key={i} className="card animate-in" style={{ animationDelay: `${Math.min(i * 60, 480)}ms` }}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
                <span className="h3" style={{ margin: 0 }}>
                  {t.name} · {ROLE_LABEL[t.role]}
                </span>
                <span className="mono" style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                  round {t.round_number} · {SENTIMENT_LABEL[t.sentiment]}
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
          <p className="eyebrow">Verdict</p>
          <p className="lede" style={{ marginBottom: 24 }}>
            {verdict.consensus_reached ? (
              <>The committee reached a <span className="voice">consensus.</span></>
            ) : (
              <>The committee <span className="voice">did not reach a consensus.</span></>
            )}
          </p>
          <p className="body-text" style={{ marginBottom: 24 }}>{verdict.risk_summary}</p>

          {verdict.blocking_stakeholders.length > 0 && (
            <div className="flag" style={{ marginBottom: 24, maxWidth: 640 }}>
              <span className="flag-k">Blockers</span>
              <p>{verdict.blocking_stakeholders.map((r) => ROLE_LABEL[r]).join(", ")}</p>
            </div>
          )}

          <div className="tbl-wrap" style={{ marginBottom: 24 }}>
            <table>
              <thead>
                <tr>
                  <th>MEDDPICC</th>
                  <th>Assessment</th>
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
                Coach — grade: <span className="mono">{verdict.seller_coaching.pitch_grade}</span>
              </p>
              <p className="body-text" style={{ maxWidth: "none" }}>
                <strong>What landed:</strong>{" "}
                {verdict.seller_coaching.what_landed.join(" · ")}
              </p>
              <p className="body-text" style={{ maxWidth: "none" }}>
                <strong>What backfired:</strong>{" "}
                {verdict.seller_coaching.what_backfired.join(" · ")}
              </p>
              <p className="body-text" style={{ maxWidth: "none", marginBottom: 0 }}>
                <strong>Rewrite it like this:</strong>{" "}
                {verdict.seller_coaching.rewrite_suggestions.join(" · ")}
              </p>
            </div>
          )}
        </div>
      )}

      <div className="section">
        <p className="eyebrow">Export</p>
        <div className="row gap-12">
          <a className="btn secondary" href={reportUrl(id, "html")} target="_blank" rel="noreferrer">
            HTML report
          </a>
          <a className="btn secondary" href={reportUrl(id, "md")} target="_blank" rel="noreferrer">
            Markdown report
          </a>
        </div>
      </div>
    </div>
  );
}
