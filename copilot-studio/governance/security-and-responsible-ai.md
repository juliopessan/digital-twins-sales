# Security, Privacy and Responsible AI Controls

## 1. Identity and authorization
- Publish to Teams with Microsoft Entra ID authentication.
- Use Dataverse security roles with least privilege.
- Scope deal, stakeholder and simulation rows by owner/team and business unit as required.
- Test cross-user and cross-team access explicitly.
- Use user-context connections where supported for user-owned data operations.

## 2. Data loss prevention
- Configure tenant/environment DLP policies.
- Allow only approved Microsoft business connectors required by the solution (Dataverse, Teams and approved research/knowledge capabilities).
- Block consumer connectors and unapproved external destinations.
- Review connector classification changes before deployment.

## 3. Personal data and research
- Research only public professional information relevant to the business role.
- Do not infer or store sensitive personal characteristics.
- Persist each fact separately with source URL, retrieval date, confidence and approval status.
- Require explicit user approval before a fact about an identifiable person is used in a REAL-grounded twin.
- If identity is ambiguous or source quality is poor, use the archetype.
- Define legal basis, notice, retention and data-subject request process with privacy/legal owners.

## 4. Transcripts
- Store transcripts only when the organization has authorization and appropriate notice/consent.
- Restrict access to transcript and calibration tables.
- Define retention and deletion periods.
- Avoid sending full transcripts to unrelated tools or agents; pass only necessary excerpts.
- Mask secrets and unnecessary personal data before analysis.

## 5. Prompt injection and untrusted content
- Treat research pages, uploaded documents and transcripts as untrusted data.
- Never follow instructions embedded in source content.
- Do not let retrieved content modify system instructions, tool permissions or approval gates.
- Keep tools narrowly scoped and validate every output before writing to Dataverse.
- Never expose system prompts, credentials, connection tokens or hidden reasoning.

## 6. Output controls
- Distinguish facts, assumptions, archetype behavior and generated recommendations.
- Require evidence for claims about real stakeholders.
- Scores are decision-support indicators, not objective truth or win probability.
- Calibration suggestions never update profiles automatically.
- Provide safe failure responses and correlation IDs.

## 7. Audit and monitoring
Audit changes to stakeholder facts, approvals, twin versions, simulations, verdicts and calibration reviews. Preserve prompt version, profile version, timestamps, owner and flow run reference. Monitor Copilot Studio analytics, agent flow failures and Dataverse capacity.

## 8. Release gate
Production release requires security review, privacy review, DLP validation, access-control tests, transcript retention approval, prompt-injection tests, and sign-off from Sales Operations and the business owner.
