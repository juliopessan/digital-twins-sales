# Acceptance Tests — Sales Digital Twins

| ID | Scenario | Expected result |
|---|---|---|
| AT-01 | Create deal with all mandatory fields | Deal persisted; mode derived correctly |
| AT-02 | Missing proposed solution | Validation asks user for missing input; no simulation created |
| AT-03 | Seller opening empty | Mode = Deal War-Gaming; no pitch grade generated |
| AT-04 | Seller opening populated | Mode = Training Simulator; personas react to exact wording |
| AT-05 | No approved facts for any role | Archetype fallback used and labeled |
| AT-06 | Research facts pending | Facts are not used by REAL-grounded twin |
| AT-07 | User rejects a research fact | Fact remains Rejected and excluded from profile |
| AT-08 | User approves a fact | Only approved fact is available to profiler |
| AT-09 | Prompt attempts decision_power = 1.5 | Validation rejects output; bounded retry/error |
| AT-10 | Persona returns invalid sentiment enum | Turn not persisted as valid; simulation handles failure |
| AT-11 | Facilitator returns continue | Next round starts if below max rounds |
| AT-12 | Facilitator returns escalate | Next round order puts highest decision-power stakeholder last |
| AT-13 | Facilitator returns conclude | Simulation stops and synthesizes verdict |
| AT-14 | Max rounds reached | Simulation concludes regardless of facilitator request |
| AT-15 | CFO blocking objection unresolved | CFO appears as blocker when supported by transcript |
| AT-16 | Champion supportive, CFO blocking | System does not claim consensus solely due to Champion |
| AT-17 | MEDDPICC dimension has no evidence | Status = Unknown, not Confirmed |
| AT-18 | Scenario changes price only | Other base deal fields remain unchanged |
| AT-19 | Scenario risk score computed | Ranking follows documented heuristic; no win probability claim |
| AT-20 | Calibration has transcript evidence | Match includes evidence excerpt |
| AT-21 | Transcript is incomplete | Missing evidence is not automatically treated as objection absent |
| AT-22 | Calibration suggests new stakeholder fact | Suggestion remains pending human review |
| AT-23 | User without deal access requests simulation | Dataverse denies access; safe error shown |
| AT-24 | Agent flow fails mid-run | Simulation marked Failed/NeedsReview; no false completion |
| AT-25 | User asks for another user's deal | Access is denied unless explicit sharing/role permits |
| AT-26 | Prompt injection in transcript | Embedded instructions are ignored as untrusted content |
| AT-27 | History lookup | Only authorized deals/simulations returned |
| AT-28 | Teams user without authentication | Sign-in required; no business data disclosed |

## Evaluation dataset

Prepare at least:
- 10 synthetic deal contexts across multiple industries.
- 4–6 committee roles per deal.
- Cases with all-archetype and mixed real/archetype profiles.
- At least 5 cases with a clear blocking objection.
- At least 5 cases with conflicting stakeholder preferences.
- At least 5 pitch variants with unsupported claims.
- Consented, reviewed call transcripts for calibration evaluation.

## Quality metrics

Track:
- Structured output validity rate.
- Simulation completion rate.
- Stakeholder coverage rate.
- Objection precision and recall on reviewed calibration data.
- MEDDPICC evidence-grounding rate.
- Human approval compliance.
- Median flow duration and failure rate.
- Cost/capacity per completed simulation where available.

A pilot is accepted only after P0 tests pass and security/privacy release gates are signed off.
