# Sales Digital Twins — Native Copilot Studio Blueprint

**Decision baseline**
- Architecture: native Microsoft Copilot Studio (standard harness)
- Persistence: Microsoft Dataverse
- Channel: Microsoft Teams
- Language: English
- Repository source: `digital-twins-sales` (Python/LangGraph reference implementation)

This package is an implementation specification and maker handoff. It is **not** an importable Power Platform solution (.zip), and it does not create agents, Dataverse tables, flows, or Teams publication automatically.

## Product direction

Rebuild the product's user-facing orchestration and simulation behaviors with Copilot Studio agents, topics, agent flows, prompts, and Dataverse. Do not deploy the original Python/LangGraph runtime as the production simulation engine in this native option.

The source repository remains the behavioral reference for:
- Deal War-Gaming and Training Simulator modes.
- Real-fact / archetype fallback.
- Buying committee roles and their decision influence.
- Facilitator decisions: continue, escalate, conclude.
- Debate transcript, verdict, MEDDPICC, pitch coaching.
- What-if scenarios and post-call calibration.

## Package map

| Path | Purpose |
|---|---|
| [prd/product-requirements.md](prd/product-requirements.md) | Product requirements and scope |
| [architecture/solution-architecture.md](architecture/solution-architecture.md) | Native target architecture and orchestration |
| [dataverse/dataverse-schema.md](dataverse/dataverse-schema.md) | Tables, columns, relationships and choices |
| [topics/topic-specifications.md](topics/topic-specifications.md) | Topics, tools, variables and flow behavior |
| [prompts/agent-prompts.md](prompts/agent-prompts.md) | Agent and task prompts |
| [deployment/deployment-runbook.md](deployment/deployment-runbook.md) | Environment setup, build, test and publish |
| [deployment/acceptance-tests.md](deployment/acceptance-tests.md) | Test scenarios and acceptance criteria |
| [governance/security-and-responsible-ai.md](governance/security-and-responsible-ai.md) | Security, privacy and operational controls |

## Important platform choice

Use the **standard Copilot Studio harness** for this blueprint because it supports authored topics, prompt tools, agent flows, Dataverse connectors, and connected agents. Keep generative orchestration enabled for intent routing, but use explicit topics/flows for state transitions, approval gates, and simulation round control.

Create one primary agent and a small set of connected specialist agents. Agent flows coordinate deterministic operations and Dataverse writes. The product is native to Power Platform; no external API or custom code service is required for the MVP.

## Implementation sequence

1. Create a Power Platform environment and solution.
2. Create Dataverse tables and choices.
3. Create specialist agents and publish them.
4. Create the orchestrator and add connected agents/tools.
5. Build agent flows for deal lifecycle, simulation, scenarios and calibration.
6. Add topics and test utterances.
7. Configure authentication, DLP and Teams channel.
8. Run acceptance tests, publish, monitor and iterate.

See the deployment runbook for exact maker steps and prerequisites.
