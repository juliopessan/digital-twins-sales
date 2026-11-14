# Dataverse Data Model

**Publisher prefix:** `dt` (confirm availability in target tenant before creation)  
**Currency:** use Dataverse transaction currency; original source sample uses USD.  
**Naming:** logical names below are proposed schema names, not pre-created Dataverse objects.

## 1. Tables

### dt_account
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_accountid | GUID primary key | Yes | Dataverse-generated |
| dt_name | Text(200) | Yes | Account name |
| dt_industry | Choice | No | Industry |
| dt_website | URL | No | Public company URL |
| dt_description | Multiline | No | Approved account context |
| ownerid | Owner | Yes | Standard ownership |

### dt_deal
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_dealid | GUID | Yes | Primary key |
| dt_name | Text(200) | Yes | Opportunity name |
| dt_accountid | Lookup(dt_account) | Yes | Parent account |
| dt_dealstage | Choice | Yes | Qualification, Discovery, Proposal, Negotiation, Closed |
| dt_dealvalue | Currency | No | Deal value |
| dt_problemstatement | Multiline | Yes | Business problem |
| dt_pitchsummary | Multiline | Yes | Proposal summary |
| dt_proposedsolution | Multiline | Yes | Solution |
| dt_selleropening | Multiline | No | Exact seller pitch |
| dt_expecteddecisiondate | Date only | No | Expected decision |
| dt_simulationmode | Choice | Yes | WarGaming, TrainingSimulator |
| dt_status | Choice | Yes | Draft, Ready, Active, Completed, Archived |

### dt_stakeholder
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_stakeholderid | GUID | Yes | Primary key |
| dt_dealid | Lookup(dt_deal) | Yes | Deal |
| dt_role | Choice | Yes | CFO, CTO, Procurement, EndUser, Champion, LegalCompliance, CEO, Security, Salesman |
| dt_displayname | Text(200) | No | Use generic role label if unknown |
| dt_company | Text(200) | No | Company |
| dt_decisionpower | Decimal(3,2) | Yes | 0.00–1.00 |
| dt_tone | Text(500) | No | Behavioral style |
| dt_isrealperson | Yes/No | Yes | Privacy classification |
| dt_approvalstatus | Choice | Yes | NotRequired, Pending, Approved, Rejected |

### dt_stakeholderfact
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_stakeholderfactid | GUID | Yes | Primary key |
| dt_stakeholderid | Lookup(dt_stakeholder) | Yes | Stakeholder |
| dt_fact | Multiline | Yes | One factual assertion |
| dt_sourceurl | URL | No | Provenance |
| dt_publisheddate | Date only | No | Source date if known |
| dt_retrievedon | Date/time | Yes | Retrieval time |
| dt_confidence | Choice | Yes | High, Medium, Low |
| dt_approvalstatus | Choice | Yes | Pending, Approved, Rejected |
| dt_approvedby | Lookup(SystemUser) | No | Reviewer |
| dt_approvedon | Date/time | No | Approval time |

### dt_digitaltwin
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_digitaltwinid | GUID | Yes | Primary key |
| dt_stakeholderid | Lookup(dt_stakeholder) | Yes | Persona |
| dt_source | Choice | Yes | Real, Archetype |
| dt_priorities | Multiline | Yes | JSON array or normalized child rows |
| dt_knownobjections | Multiline | Yes | JSON array or normalized child rows |
| dt_groundingfacts | Multiline | No | Only approved facts |
| dt_profileversion | Text(40) | Yes | Immutable profile version |
| dt_promptversion | Text(40) | Yes | Prompt version |
| dt_isactive | Yes/No | Yes | Current profile |

### dt_simulation
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_simulationid | GUID | Yes | Primary key |
| dt_name | Text(200) | Yes | Human-readable label |
| dt_dealid | Lookup(dt_deal) | Yes | Deal |
| dt_status | Choice | Yes | Queued, Running, Completed, Failed, NeedsReview |
| dt_simulationmode | Choice | Yes | WarGaming, TrainingSimulator |
| dt_maxrounds | Whole number | Yes | Default 3; max configured |
| dt_overallsentiment | Choice | No | Supportive, Neutral, Skeptical, Blocking |
| dt_consensusreached | Yes/No | No | Verdict |
| dt_blockingstakeholders | Multiline | No | JSON array of role values |
| dt_topobjections | Multiline | No | JSON array |
| dt_risksummary | Multiline | No | Synthesized risk |
| dt_riskscore | Decimal | No | Comparative heuristic, not win probability |
| dt_promptversion | Text(40) | Yes | Orchestrator/synthesis prompt version |
| dt_startedon | Date/time | No | Start |
| dt_completedon | Date/time | No | Completion |
| dt_errorcode | Text(100) | No | Failure code |
| dt_errordetail | Multiline | No | Sanitized error |

### dt_debateturn
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_debateturnid | GUID | Yes | Primary key |
| dt_simulationid | Lookup(dt_simulation) | Yes | Parent |
| dt_roundnumber | Whole number | Yes | 1..MaxRounds |
| dt_sequence | Whole number | Yes | Order within simulation |
| dt_role | Choice | Yes | Stakeholder role |
| dt_statement | Multiline | Yes | Generated statement |
| dt_objections | Multiline | No | JSON array |
| dt_sentiment | Choice | Yes | Supportive, Neutral, Skeptical, Blocking |
| dt_promptversion | Text(40) | Yes | Prompt provenance |

### dt_assessment
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_assessmentid | GUID | Yes | Primary key |
| dt_simulationid | Lookup(dt_simulation) | Yes | Simulation |
| dt_dimension | Choice | Yes | Metrics, EconomicBuyer, DecisionCriteria, DecisionProcess, PaperProcess, IdentifyPain, Champion, Competition |
| dt_status | Choice | Yes | Confirmed, Partial, Unknown, AtRisk |
| dt_evidence | Multiline | No | Evidence |
| dt_gaps | Multiline | No | Gaps |
| dt_nextquestion | Multiline | No | Discovery question |

### dt_scenario
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_scenarioid | GUID | Yes | Primary key |
| dt_basesimulationid | Lookup(dt_simulation) | Yes | Base run |
| dt_name | Text(150) | Yes | Scenario name |
| dt_description | Multiline | No | Delta description |
| dt_overrides | Multiline | Yes | JSON of explicitly changed fields |
| dt_resultsimulationid | Lookup(dt_simulation) | No | Result run |
| dt_riskscore | Decimal | No | Comparative ranking |

### dt_calibration
| Column | Type | Required | Notes |
|---|---|---:|---|
| dt_calibrationid | GUID | Yes | Primary key |
| dt_simulationid | Lookup(dt_simulation) | Yes | Predicted simulation |
| dt_transcripttext | Multiline | Yes | Actual call transcript; apply retention/access controls |
| dt_overallfidelity | Decimal(5,4) | No | Confirmed predictions / evaluated predictions |
| dt_matches | Multiline | No | JSON match records and evidence |
| dt_blindspots | Multiline | No | JSON array |
| dt_enrichmentsuggestions | Multiline | No | Suggestions, not automatic writes |
| dt_reviewstatus | Choice | Yes | Pending, Approved, Rejected |

## 2. Relationships

- Account 1:N Deal
- Deal 1:N Stakeholder
- Stakeholder 1:N StakeholderFact
- Stakeholder 1:N DigitalTwin (retain versions)
- Deal 1:N Simulation
- Simulation 1:N DebateTurn
- Simulation 1:N Assessment
- Simulation 1:N Scenario
- Simulation 1:N Calibration

## 3. Choices

Create global choices for role, sentiment, source, approval status, simulation status/mode, deal stage, assessment status, confidence and calibration review status. Keep stored choice values stable across environments.

## 4. Data design rules

- Use lookups, not account/deal names as relational keys.
- Use Dataverse ownership and security model; do not rely on hidden columns as authorization.
- Keep facts atomic (one assertion per row) so approval and provenance are granular.
- Use immutable version fields for profiles and prompts.
- For arrays, JSON text is acceptable for MVP outputs; normalize high-volume or query-critical collections later.
- Enable auditing for stakeholder facts, approval fields, simulation status, verdict and calibration.
- Define retention and deletion policies before storing real meeting transcripts.
- Avoid storing sensitive personal data. Do not infer or persist sensitive traits.
