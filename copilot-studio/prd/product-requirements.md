# Product Requirements Document — Sales Digital Twins

**Version:** 1.0  
**Status:** Approved design baseline  
**Target platform:** Microsoft Copilot Studio (standard harness)  
**Channel:** Microsoft Teams  
**Persistence:** Microsoft Dataverse  
**Application language:** English

## 1. Product vision

Enable enterprise B2B sellers to rehearse complex negotiations with a synthetic buying committee before real customer meetings. The application creates stakeholder digital twins grounded in approved account facts or curated role archetypes, runs a structured committee debate, and returns actionable deal intelligence.

## 2. Problem statement

Enterprise sales teams discover objections late, have incomplete stakeholder maps, and rely on inconsistent individual preparation. Sales Digital Twins provides a repeatable rehearsal process that exposes financial, technical, procurement, security, legal and business objections before the customer meeting.

## 3. Goals

- Prepare sellers for high-value and complex B2B opportunities.
- Identify stakeholder objections and potential vetoes.
- Evaluate seller opening pitches using the actual supplied wording.
- Assess opportunity evidence using MEDDPICC.
- Compare alternative deal configurations.
- Calibrate simulated objections against real meeting outcomes.
- Preserve traceability of source facts, prompt versions and simulation outcomes.

## 4. Non-goals for MVP

- Automated CRM write-back or Dynamics 365 synchronization.
- Autonomous outreach to real stakeholders.
- Predicting win probability.
- Real-time voice/video meeting participation.
- Learning or updating real-person profiles without human approval.
- Replacing a human sales methodology owner or legal/compliance review.

## 5. Users and jobs to be done

| User | Job |
|---|---|
| Account Executive | Rehearse a pitch and anticipate objections |
| Account Manager | Identify stakeholder and deal risks |
| Sales Director | Review deal readiness and coaching recommendations |
| Sales Enablement | Standardize preparation and coaching |
| Sales Operations | Analyze adoption and simulation quality |

## 6. Product modes

### 6.1 Deal War-Gaming
When Seller Opening is empty, the committee evaluates the opportunity summary and proposed solution autonomously. The seller receives a committee verdict and recommended talk track.

### 6.2 Training Simulator
When Seller Opening is supplied, personas react to the seller's exact words. The Coach evaluates what landed, what backfired, and provides line-by-line rewrites.

## 7. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Create and validate account/opportunity context | P0 |
| FR-02 | Configure committee roles | P0 |
| FR-03 | Create archetype personas when approved real facts are absent | P0 |
| FR-04 | Capture research facts with source URL and approval status | P1 |
| FR-05 | Run a multi-round committee debate | P0 |
| FR-06 | Facilitator selects continue, escalate or conclude | P0 |
| FR-07 | Generate structured verdict and transcript | P0 |
| FR-08 | Generate MEDDPICC assessment with evidence and gaps | P0 |
| FR-09 | Evaluate Seller Opening when supplied | P1 |
| FR-10 | Compare what-if scenarios | P1 |
| FR-11 | Calibrate simulation against real meeting transcript | P1 |
| FR-12 | Persist records and support history lookup | P0 |
| FR-13 | Generate an executive summary in English | P0 |
| FR-14 | Enforce human approval before real-person facts are used | P0 |
| FR-15 | Preserve prompt and rubric versions per simulation | P0 |

## 8. Non-functional requirements

- Identity: Microsoft Entra ID authentication through Teams.
- Authorization: Dataverse security roles and row ownership/team access.
- Data protection: Power Platform DLP policies and environment controls.
- Auditability: created/modified metadata, approval history, prompt version and simulation trace.
- Reliability: explicit error states; no fabricated completion.
- Performance: show progress for long simulations; use bounded rounds and bounded committee size.
- Accessibility: clear text, keyboard-friendly Teams interactions, no color-only status indicators.
- Localization: English prompts and user-facing responses for MVP.
- Maintainability: prompts, topics, choices and flows managed in a Power Platform solution.

## 9. User journey

1. User opens Sales Digital Twins in Teams.
2. User creates a deal and enters account, stage, problem, solution and pitch summary.
3. User chooses committee roles and optionally adds known stakeholder information.
4. Research facts, if any, are reviewed and approved by the user.
5. The system creates each digital twin from approved facts or role archetype.
6. User confirms simulation mode and parameters.
7. Simulation runs for up to three rounds by default.
8. User receives transcript, verdict, blockers, MEDDPICC and recommended actions.
9. User can compare scenarios or submit a real call transcript for calibration.
10. Simulation and all derived records are persisted in Dataverse.

## 10. Success metrics

Initial targets are hypotheses to validate during pilot:
- 100% of completed simulations persist a structured result.
- 100% of real-person grounding facts used have approval status = Approved.
- 100% of simulation outputs carry prompt/rubric version.
- At least 80% of configured committee roles produce a valid turn, excluding documented failures.
- Track objection precision/recall against a consented and reviewed calibration dataset.
- Measure median preparation time before and after adoption.

Do not interpret a synthetic score as a statistical probability of deal closure.

## 11. MVP release boundary

P0 includes deal setup, archetypes, committee simulation, facilitator control, transcript, verdict, MEDDPICC, history and governance. P1 includes web research with approval, pitch coaching, scenario comparison and calibration. Release P0 as a controlled pilot before enabling P1.

## 12. Assumptions and dependencies

- A Power Platform environment with Dataverse is available.
- Copilot Studio licensing and required capacity are provisioned.
- Makers can create agents, topics, prompts, agent flows and Dataverse tables.
- Teams app deployment is approved by tenant administrators.
- No external custom API is used in the native implementation.
- Product owner approves archetypes, evaluation rubrics and data retention policy.
