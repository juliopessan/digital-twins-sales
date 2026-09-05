"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createRun, getAccount, listAccounts, researchStakeholder } from "@/lib/api";
import type { AccountContext, AccountSummary, StakeholderRole } from "@/lib/types";
import { ROLE_LABEL_PT } from "@/lib/types";

const ALL_ROLES: StakeholderRole[] = [
  "champion",
  "cto",
  "cfo",
  "procurement",
  "ceo",
  "end_user",
  "legal_compliance",
  "security",
];

const DEFAULT_COMMITTEE: StakeholderRole[] = ["champion", "cto", "cfo", "procurement"];

function emptyAccount(): AccountContext {
  return {
    account_name: "",
    deal_stage: "Proposta enviada, aguardando revisão do comitê",
    pitch_summary: "",
    proposed_solution: "",
    deal_value_usd: null,
    seller_opening: null,
    real_data: {},
    real_names: {},
    roles_in_committee: DEFAULT_COMMITTEE,
  };
}

export default function SetupPage() {
  const router = useRouter();

  const [mode, setMode] = useState<"pick" | "manual">("pick");
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [pickedAccount, setPickedAccount] = useState<AccountContext | null>(null);

  const [manual, setManual] = useState<AccountContext>(emptyAccount());
  const [realRole, setRealRole] = useState<StakeholderRole>("champion");
  const [realName, setRealName] = useState("");
  const [realFacts, setRealFacts] = useState("");

  const [exaKey, setExaKey] = useState("");
  const [researching, setResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);

  const [sellerOpening, setSellerOpening] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [maxRounds, setMaxRounds] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    listAccounts()
      .then((list) => {
        setAccounts(list);
        if (list.length > 0) setSelectedId(list[0].id);
      })
      .catch((e) => setFormError(`Não foi possível carregar as contas: ${e.message}`));
  }, []);

  useEffect(() => {
    if (mode !== "pick" || !selectedId) return;
    getAccount(selectedId).then(setPickedAccount).catch((e) => setFormError(e.message));
  }, [mode, selectedId]);

  function toggleCommitteeRole(role: StakeholderRole) {
    setManual((m) => {
      const has = m.roles_in_committee.includes(role);
      return {
        ...m,
        roles_in_committee: has
          ? m.roles_in_committee.filter((r) => r !== role)
          : [...m.roles_in_committee, role],
      };
    });
  }

  async function handleResearch() {
    setResearchError(null);
    if (!manual.account_name || !realName || !exaKey) {
      setResearchError("Preencha empresa, nome do stakeholder e a EXA API Key antes de pesquisar.");
      return;
    }
    setResearching(true);
    try {
      const { facts } = await researchStakeholder(
        realName,
        ROLE_LABEL_PT[realRole],
        manual.account_name,
        exaKey
      );
      setRealFacts(facts.join("\n"));
    } catch (e) {
      setResearchError(e instanceof Error ? e.message : String(e));
    } finally {
      setResearching(false);
    }
  }

  function buildManualAccount(): AccountContext | null {
    if (!manual.account_name || !manual.pitch_summary || !manual.proposed_solution) return null;
    if (manual.roles_in_committee.length === 0) return null;

    const facts = realFacts
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    return {
      ...manual,
      real_data: facts.length > 0 ? { [realRole]: facts } : {},
      real_names: facts.length > 0 && realName ? { [realRole]: realName } : {},
    };
  }

  async function handleSubmit() {
    setFormError(null);
    const base = mode === "pick" ? pickedAccount : buildManualAccount();
    if (!base) {
      setFormError(
        mode === "pick"
          ? "Escolha uma conta."
          : "Preencha empresa, pitch, solução proposta e ao menos um papel no comitê."
      );
      return;
    }
    if (!apiKey.trim()) {
      setFormError("Informe a Anthropic API Key.");
      return;
    }
    const account: AccountContext = {
      ...base,
      seller_opening: sellerOpening.trim() || null,
    };
    setSubmitting(true);
    try {
      const { run_id } = await createRun(account, apiKey.trim(), maxRounds);
      router.push(`/runs/${run_id}`);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  }

  return (
    <div className="page" style={{ paddingTop: 68, paddingBottom: 68 }}>
      <p className="eyebrow">Sales Digital Twins</p>
      <h1 className="display" style={{ marginBottom: 14 }}>
        Ensaie o pior comitê da sua vida,{" "}
        <span className="voice">antes que ele seja real.</span>
      </h1>
      <p className="lede" style={{ marginBottom: 48 }}>
        Um comitê de compra sintético — grounded em dados reais quando existem,
        arquétipo quando não — debate a sua proposta. Cole o seu pitch e o
        coach avalia como ele se sustentou; deixe em branco e o comitê
        debate sozinho.
      </p>

      <div className="section" style={{ paddingTop: 0 }}>
        <div className="row gap-12" style={{ marginBottom: 24 }}>
          <button
            className={`btn ${mode === "pick" ? "" : "secondary"}`}
            onClick={() => setMode("pick")}
          >
            Escolher conta
          </button>
          <button
            className={`btn ${mode === "manual" ? "" : "secondary"}`}
            onClick={() => setMode("manual")}
          >
            Digitar manualmente
          </button>
        </div>

        {mode === "pick" && (
          <div className="field" style={{ maxWidth: 480 }}>
            <label>Conta</label>
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.account_name}
                </option>
              ))}
            </select>
            {pickedAccount && (
              <div className="card" style={{ marginTop: 16 }}>
                <p className="body-text" style={{ marginBottom: 8 }}>
                  <strong>Pitch:</strong> {pickedAccount.pitch_summary}
                </p>
                <p className="body-text" style={{ margin: 0 }}>
                  <strong>Comitê:</strong>{" "}
                  {pickedAccount.roles_in_committee.map((r) => ROLE_LABEL_PT[r]).join(", ")}
                </p>
              </div>
            )}
          </div>
        )}

        {mode === "manual" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
            <div>
              <div className="field">
                <label>Empresa</label>
                <input
                  value={manual.account_name}
                  onChange={(e) => setManual({ ...manual, account_name: e.target.value })}
                  placeholder="Ex: iFood"
                />
              </div>
              <div className="field">
                <label>Resumo do pitch</label>
                <textarea
                  value={manual.pitch_summary}
                  onChange={(e) => setManual({ ...manual, pitch_summary: e.target.value })}
                  placeholder="O que está sendo vendido e para quem"
                />
              </div>
              <div className="field">
                <label>Solução proposta</label>
                <textarea
                  value={manual.proposed_solution}
                  onChange={(e) => setManual({ ...manual, proposed_solution: e.target.value })}
                  placeholder="Detalhes técnicos/comerciais da proposta"
                />
              </div>
              <div className="field">
                <label>Papéis no comitê</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {ALL_ROLES.map((role) => (
                    <button
                      key={role}
                      type="button"
                      className="pill"
                      style={
                        manual.roles_in_committee.includes(role)
                          ? { background: "var(--ink)", color: "var(--paper)", borderColor: "var(--ink)" }
                          : undefined
                      }
                      onClick={() => toggleCommitteeRole(role)}
                    >
                      {ROLE_LABEL_PT[role]}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <p className="h3">Stakeholder real (digital twin)</p>
              <div className="field">
                <label>Qual papel é o stakeholder real?</label>
                <select value={realRole} onChange={(e) => setRealRole(e.target.value as StakeholderRole)}>
                  {manual.roles_in_committee.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABEL_PT[r]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Nome do stakeholder</label>
                <input
                  value={realName}
                  onChange={(e) => setRealName(e.target.value)}
                  placeholder="Ex: Diego Barreto"
                />
              </div>
              <div className="field">
                <label>EXA API Key (opcional, para pesquisa automática)</label>
                <input
                  type="password"
                  value={exaKey}
                  onChange={(e) => setExaKey(e.target.value)}
                />
                <div className="hint">Usada só em memória nesta sessão — não é salva.</div>
              </div>
              <button
                type="button"
                className="btn secondary"
                onClick={handleResearch}
                disabled={researching}
                style={{ marginBottom: 16 }}
              >
                {researching ? "Pesquisando..." : "🔎 Pesquisar fatos com EXA"}
              </button>
              {researchError && (
                <div className="flag" style={{ marginBottom: 16 }}>
                  <p>{researchError}</p>
                </div>
              )}
              <div className="field">
                <label>Fatos conhecidos (um por linha)</label>
                <textarea
                  value={realFacts}
                  onChange={(e) => setRealFacts(e.target.value)}
                  placeholder={"Ex: Assumiu como CEO em 2026\nFoco declarado em IA generativa"}
                  style={{ minHeight: 120 }}
                />
                <div className="hint">
                  Sem fatos, esse papel também cai para o arquétipo genérico.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="section">
        <div className="field" style={{ maxWidth: 640 }}>
          <label>Sua fala de abertura (opcional)</label>
          <textarea
            value={sellerOpening}
            onChange={(e) => setSellerOpening(e.target.value)}
            placeholder="Cole o pitch como você vai dizer. Se preenchido, as personas reagem às suas palavras reais e um Coach avalia seu pitch no final."
            style={{ minHeight: 110 }}
          />
        </div>

        <div style={{ display: "flex", gap: 32, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ width: 320 }}>
            <label>Anthropic API Key</label>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
            <div className="hint">Usada só em memória nesta sessão — não é salva.</div>
          </div>
          <div className="field" style={{ width: 200 }}>
            <label>Máximo de rounds: {maxRounds}</label>
            <input
              type="range"
              min={1}
              max={5}
              value={maxRounds}
              onChange={(e) => setMaxRounds(Number(e.target.value))}
            />
          </div>
        </div>

        {formError && (
          <div className="flag" style={{ maxWidth: 640, marginBottom: 20 }}>
            <p>{formError}</p>
          </div>
        )}

        <button className="btn" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Iniciando..." : "Rodar simulação →"}
        </button>
      </div>
    </div>
  );
}
