# Copilot Studio Topics, Tools and Agent Flow Specifications

## 1. Primary agent configuration

**Name:** Sales Digital Twins Orchestrator  
**Harness:** Standard Copilot Studio harness  
**Language:** English  
**Channel:** Microsoft Teams  
**Generative orchestration:** Enabled  
**Authentication:** Microsoft Entra ID  
**Knowledge:** Dataverse tables for approved account/deal context and archetype guidance. Do not expose all operational tables as unrestricted generative knowledge; use scoped Dataverse actions for transactional data.

### Agent description
An enterprise B2B sales rehearsal assistant that creates synthetic buying committees, simulates stakeholder objections, assesses MEDDPICC evidence, coaches seller pitches, compares deal scenarios and calibrates predictions against actual meetings.

## 2. Topics

| ID | Topic | Example trigger phrases | Required inputs |
|---|---|---|---|
| T01 | Welcome and Help | Start, help, what can you do | None |
| T02 | Create Deal | Create a deal, rehearse an opportunity | Account, deal, problem, solution, stage |
| T03 | Update Deal | Update this opportunity | Deal ID and changed fields |
| T04 | Configure Committee | Add CFO, include CISO | Deal ID, roles |
| T05 | Research Stakeholders | Research the buying committee | Company, roles, optional names |
| T06 | Review Research | Approve these facts | Fact IDs and decisions |
| T07 | Build Digital Twins | Prepare stakeholder twins | Deal ID |
| T08 | Run Simulation | Simulate this deal, war-game this pitch | Deal ID, mode, max rounds |
| T09 | View Simulation | Show the result | Simulation ID |
| T10 | Coach My Pitch | Review my opening pitch | Seller opening |
| T11 | MEDDPICC Review | Assess MEDDPICC | Deal/simulation ID |
| T12 | Compare Scenarios | Compare discount vs POC | Base deal and scenario deltas |
| T13 | Calibrate Simulation | Compare against actual call | Simulation ID, transcript |
| T14 | Deal History | Show my simulations | Deal/account filter |
| T15 | Governance Help | Explain data usage | None |

## 3. Agent flow specifications

### AF01 — CreateOrUpdateDeal
Inputs: account name, industry, deal name, stage, problem statement, pitch summary, proposed solution, deal value, seller opening, expected decision date.
Steps: validate required values; upsert account; create/update deal; derive mode from seller opening; return deal ID, mode and validation messages.
Outputs: deal ID, status, mode.

### AF02 — ResearchAndApproveCommittee
Inputs: company, committee roles and optional names.
Steps: research using approved Copilot Studio research capability/web grounding; return facts with source URLs and confidence; create StakeholderFact rows with Pending status; show user a review card/topic; update each fact only after explicit approval.
Outputs: approved/rejected/pending counts. If no reliable facts, continue with archetypes.

### AF03 — BuildDigitalTwins
Inputs: deal ID.
Steps: retrieve selected stakeholders; retrieve only Approved facts; call Profiler; validate role, source, decision power 0..1, priorities and objections; create versioned DigitalTwin records. If no approved facts, use archetype prompt.
Outputs: profile IDs, source per role, missing/failed roles.

### AF04 — RunCommitteeSimulation
Inputs: deal ID, max rounds (default 3, configured maximum 3 for MVP).
Steps:
1. Create Simulation with status Running and prompt version.
2. Load active twin profiles and deal context.
3. Set round = 1 and speaking order.
4. Iterate selected speakers in order; call role-conditioned Stakeholder Twin prompt with transcript-so-far; validate output; create DebateTurn.
5. Call Facilitator with current-round transcript.
6. If decision = escalate, sort next round by decision power ascending so the highest decision power speaks last (match reference implementation's escalation behavior); if continue, retain base order.
7. Continue while decision in [continue, escalate] and round < max rounds.
8. Call Sales Coach only in Training Simulator mode.
9. Call MEDDPICC assessment and verdict synthesis.
10. Persist assessment and verdict; set Completed.
11. On failure, set Failed/NeedsReview and return safe error; never synthesize missing turns.
Outputs: simulation ID, status, sentiment, consensus, blockers, objections, MEDDPICC summary, coaching summary.

**Loop safety:** set a hard upper bound on roles × rounds and a maximum retry count for malformed outputs. Use flow variables for transient iteration state and Dataverse for durable state. Validate actual agent-flow loop/action limits in the target environment.

### AF05 — CompareScenarios
Inputs: base deal ID and scenario collection (name, description, explicit field overrides).
Steps: create independent simulation records for each branch; copy base context; apply only declared overrides; call AF04 per branch or a reusable simulation child flow; compute comparable risk rank; persist Scenario records; return ordered comparison.
Risk rank follows reference logic: sentiment weight (supportive 0, neutral 1, skeptical 2, blocking 3) + blocker count + 1 when consensus is false. It is a relative ranking, not a probability.

### AF06 — CalibrateAgainstCall
Inputs: simulation ID and transcript.
Steps: retrieve predicted objections; compare semantically against transcript; require transcript evidence for confirmed match; record unconfirmed predictions and blind spots; create Calibration record Pending review; never update stakeholder facts automatically.
Outputs: fidelity, matches, blind spots, enrichment suggestions.

### AF07 — GenerateExecutiveSummary
Inputs: simulation ID.
Steps: retrieve simulation, turns, assessments and coaching; produce English report with facts vs inferences clearly labeled; return report text and Dataverse record reference. Optional export to a document can be a later enhancement.

## 4. Prompt tools

Create prompt tools or agent instructions for:
- Research summary
- Persona profiling
- Role-conditioned stakeholder response
- Facilitator decision
- Verdict synthesis
- MEDDPICC assessment
- Pitch coaching
- Scenario comparison
- Post-call calibration
- Executive summary

Full prompt text is in ../prompts/agent-prompts.md.

## 5. Conversation variables

Use topic-scoped variables where possible. Suggested global variables only for active conversation context:
- Global.ActiveDealId (Text)
- Global.ActiveSimulationId (Text)
- Global.ActiveMode (Text)
- Global.LastActionStatus (Text)

Do not keep complete transcripts, full profiles or durable arrays in global conversation variables. Retrieve them from Dataverse by ID.

## 6. Error handling

Standard statuses: VALIDATION_ERROR, NOT_FOUND, APPROVAL_REQUIRED, INVALID_AGENT_OUTPUT, FLOW_TIMEOUT, PERMISSION_DENIED, DEPENDENCY_FAILURE, INTERNAL_ERROR.
Return a correlation ID and user-safe message. Store sanitized diagnostic details in Dataverse/flow run history. Do not expose connector payloads, system prompts or personal data in error messages.
