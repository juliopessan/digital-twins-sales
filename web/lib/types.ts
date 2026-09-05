// Mirrors digital_twins/models.py. Kept intentionally 1:1 with the Pydantic
// shapes so a payload from the API needs no transformation to render.

export type StakeholderRole =
  | "salesman"
  | "cfo"
  | "cto"
  | "procurement"
  | "end_user"
  | "champion"
  | "legal_compliance"
  | "ceo"
  | "security";

export const ROLE_LABEL_PT: Record<StakeholderRole, string> = {
  salesman: "Vendedor",
  ceo: "CEO",
  cto: "CTO",
  cfo: "CFO",
  procurement: "Procurement",
  champion: "Champion interno",
  end_user: "Usuário final",
  legal_compliance: "Jurídico/Compliance",
  security: "Segurança",
};

export type DataSource = "real" | "archetype";

export type Sentiment = "supportive" | "neutral" | "skeptical" | "blocking";

export const SENTIMENT_LABEL_PT: Record<Sentiment, string> = {
  supportive: "Favorável",
  neutral: "Neutro",
  skeptical: "Cético",
  blocking: "Bloqueador",
};

export interface StakeholderProfile {
  role: StakeholderRole;
  name: string;
  company: string;
  source: DataSource;
  priorities: string[];
  known_objections: string[];
  decision_power: number;
  tone: string;
  grounding_facts: string[];
  system_prompt?: string | null;
}

export interface AccountContext {
  account_name: string;
  deal_stage: string;
  pitch_summary: string;
  proposed_solution: string;
  deal_value_usd?: number | null;
  seller_opening?: string | null;
  real_data: Partial<Record<StakeholderRole, string[]>>;
  real_names: Partial<Record<StakeholderRole, string>>;
  roles_in_committee: StakeholderRole[];
}

export interface DebateTurn {
  round_number: number;
  role: StakeholderRole;
  name: string;
  statement: string;
  objections_raised: string[];
  sentiment: Sentiment;
}

export interface SellerCoaching {
  pitch_grade: string;
  what_landed: string[];
  what_backfired: string[];
  rewrite_suggestions: string[];
}

export interface DebateVerdict {
  consensus_reached: boolean;
  overall_sentiment: Sentiment;
  top_objections: string[];
  blocking_stakeholders: StakeholderRole[];
  recommended_talk_track: string[];
  risk_summary: string;
  meddpicc_scorecard: Record<string, string>;
  seller_coaching?: SellerCoaching | null;
}

export interface RunResult {
  account: AccountContext;
  personas: StakeholderProfile[];
  transcript: DebateTurn[];
  verdict: DebateVerdict | null;
  duration_seconds: number;
  llm_calls: number;
  model_persona: string;
  model_facilitator: string;
  model_synthesizer: string;
  slug: string;
  finished_at: string;
}

export type RunStatus = "running" | "done" | "error";

export interface RunEvent {
  event: "start" | "done";
  agent: string;
}

export interface RunSnapshot {
  run_id: string;
  status: RunStatus;
  log: RunEvent[];
  result: RunResult | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface AccountSummary {
  id: string;
  account_name: string;
  deal_stage: string;
  deal_value_usd?: number | null;
}
