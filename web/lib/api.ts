import type {
  AccountContext,
  AccountSummary,
  RunSnapshot,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    let message = body;
    try {
      message = JSON.parse(body).detail ?? body;
    } catch {
      // keep raw body
    }
    throw new Error(message || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function listAccounts(): Promise<AccountSummary[]> {
  return fetch(`${API_URL}/api/accounts`).then((r) => json(r));
}

export function getAccount(id: string): Promise<AccountContext> {
  return fetch(`${API_URL}/api/accounts/${id}`).then((r) => json(r));
}

export function createRun(
  account: AccountContext,
  apiKey: string,
  maxRounds: number
): Promise<{ run_id: string }> {
  return fetch(`${API_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account, api_key: apiKey, max_rounds: maxRounds }),
  }).then((r) => json(r));
}

export function getRun(runId: string): Promise<RunSnapshot> {
  return fetch(`${API_URL}/api/runs/${runId}`, { cache: "no-store" }).then((r) =>
    json(r)
  );
}

export function researchStakeholder(
  name: string,
  roleLabel: string,
  company: string,
  exaApiKey: string
): Promise<{ facts: string[] }> {
  return fetch(`${API_URL}/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      role_label: roleLabel,
      company,
      exa_api_key: exaApiKey,
    }),
  }).then((r) => json(r));
}

export function reportUrl(runId: string, kind: "md" | "html"): string {
  return `${API_URL}/api/runs/${runId}/report.${kind}`;
}

export { API_URL };
