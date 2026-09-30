"use client";

import { useEffect, useState } from "react";
import { researchCommittee } from "@/lib/api";
import type { StakeholderRole } from "@/lib/types";
import { ROLE_LABEL } from "@/lib/types";

export interface MappedRole {
  name: string;
  facts: string[]; // only the facts the seller approved
}
export type Mapping = Partial<Record<StakeholderRole, MappedRole>>;

interface Row {
  name: string;
  facts: { text: string; keep: boolean }[];
  sources: string[];
  error: string | null;
  researched: boolean;
}

interface Props {
  company: string;
  roles: StakeholderRole[];
  existingFacts: Partial<Record<StakeholderRole, string[]>>;
  exaKey: string;
  onExaKeyChange: (v: string) => void;
  onChange: (m: Mapping) => void;
}

const emptyRow = (): Row => ({ name: "", facts: [], sources: [], error: null, researched: false });

// Sources come from an external search index — only ever link http(s).
const safeUrl = (u: string) => (/^https?:\/\//i.test(u) ? u : null);
const host = (u: string) => {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return u;
  }
};

export default function CommitteeMapper({ company, roles, existingFacts, exaKey, onExaKeyChange, onChange }: Props) {
  const committee = roles.filter((r) => r !== "salesman");
  const [rows, setRows] = useState<Partial<Record<StakeholderRole, Row>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const mapping: Mapping = {};
    for (const role of committee) {
      const row = rows[role];
      if (!row) continue;
      const approved = row.facts.filter((f) => f.keep).map((f) => f.text);
      if (approved.length > 0) mapping[role] = { name: row.name.trim(), facts: approved };
    }
    onChange(mapping);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  function patch(role: StakeholderRole, p: Partial<Row>) {
    setRows((r) => ({ ...r, [role]: { ...(r[role] ?? emptyRow()), ...p } }));
  }

  async function run() {
    setError(null);
    if (!company.trim()) return setError("Choose or fill in the company first.");
    if (!exaKey.trim()) return setError("Enter the EXA API key to research the committee.");
    setBusy(true);
    try {
      const { results } = await researchCommittee(
        company,
        committee.map((role) => ({ role, role_label: ROLE_LABEL[role], name: rows[role]?.name?.trim() || undefined })),
        exaKey.trim()
      );
      setRows((prev) => {
        const next = { ...prev };
        for (const r of results) {
          next[r.role] = {
            name: prev[r.role]?.name?.trim() || r.name,
            facts: r.facts.map((text) => ({ text, keep: true })),
            sources: r.sources,
            error: r.error,
            researched: true,
          };
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const grounded = committee.filter(
    (r) => (existingFacts[r]?.length ?? 0) > 0 || rows[r]?.facts.some((f) => f.keep)
  ).length;

  return (
    <div className="section">
      <p className="eyebrow">Map the committee (optional)</p>
      <p className="body-text" style={{ marginBottom: 20 }}>
        Research each stakeholder before the debate. Facts you approve ground that persona in real data;
        any role left without facts stays a generic archetype. Review every fact — web search can pick
        the wrong person.
      </p>

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 8 }}>
        <div className="field" style={{ width: 320 }}>
          <label>EXA API key</label>
          <input type="password" value={exaKey} onChange={(e) => onExaKeyChange(e.target.value)} />
          <div className="hint">Only kept in memory for this session — never saved.</div>
        </div>
        <div className="field">
          <button type="button" className="btn secondary" onClick={run} disabled={busy || committee.length === 0}>
            {busy ? "Researching…" : "🔎 Research committee"}
          </button>
        </div>
      </div>

      {error && (
        <div className="flag" style={{ maxWidth: 640, marginBottom: 20 }}>
          <p>{error}</p>
        </div>
      )}

      <div className="stack">
        {committee.map((role) => {
          const row = rows[role] ?? emptyRow();
          const existing = existingFacts[role]?.length ?? 0;
          return (
            <div className="card" key={role}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap" }}>
                <span className="h3" style={{ margin: 0 }}>{ROLE_LABEL[role]}</span>
                <span className="mono" style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                  {existing > 0 ? `${existing} fact${existing > 1 ? "s" : ""} already in the account file` : "no facts yet"}
                </span>
              </div>
              <input
                value={row.name}
                onChange={(e) => patch(role, { name: e.target.value })}
                placeholder={`Name (optional — otherwise we look up the current ${ROLE_LABEL[role]})`}
                style={{ marginBottom: 12 }}
              />
              {row.error && (
                <div className="flag" style={{ marginBottom: 8 }}>
                  <p>{row.error}</p>
                </div>
              )}
              {row.facts.map((f, i) => (
                <label
                  key={i}
                  style={{
                    display: "flex", gap: 10, alignItems: "flex-start", textTransform: "none",
                    letterSpacing: 0, fontSize: 13.5, color: "var(--ink-soft)", marginBottom: 8, cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={f.keep}
                    style={{ width: "auto", marginTop: 4, flex: "none" }}
                    onChange={(e) =>
                      patch(role, { facts: row.facts.map((x, j) => (j === i ? { ...x, keep: e.target.checked } : x)) })
                    }
                  />
                  <span style={{ opacity: f.keep ? 1 : 0.45 }}>{f.text}</span>
                </label>
              ))}
              {row.sources.length > 0 && (
                <p className="mono" style={{ fontSize: 11, color: "var(--ink-faint)", margin: "8px 0 0" }}>
                  Sources:{" "}
                  {row.sources.map((u, i) => {
                    const href = safeUrl(u);
                    return (
                      <span key={u}>
                        {i > 0 && " · "}
                        {href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer">{host(u)}</a>
                        ) : (
                          host(u)
                        )}
                      </span>
                    );
                  })}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <p className="mono" style={{ fontSize: 11.5, color: "var(--ink-faint)", marginTop: 16 }}>
        {grounded} of {committee.length} roles will be grounded in real data
      </p>
    </div>
  );
}
