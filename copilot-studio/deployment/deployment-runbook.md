# Deployment Runbook — Native Sales Digital Twins

## 0. Prerequisites

- Power Platform environment with full Dataverse (not Dataverse for Teams).
- Copilot Studio access and licensing/capacity confirmed.
- Permission to create a solution, tables, choices, agents, topics and agent flows.
- Microsoft Teams app publishing approval.
- Environment strategy: Development, Test, Production.
- Security, privacy and DLP owners identified.

## 1. Create solution

1. Open Power Apps maker portal and select Development environment.
2. Create a solution named **Sales Digital Twins**.
3. Publisher prefix: `dt` (confirm no collision).
4. Add environment variables only for non-secret configuration such as default max rounds and pilot support contact.
5. Use connection references for Dataverse and any approved connectors.

## 2. Create Dataverse schema

1. Create global choices listed in dataverse-schema.md.
2. Create tables in dependency order: Account, Deal, Stakeholder, StakeholderFact, DigitalTwin, Simulation, DebateTurn, Assessment, Scenario, Calibration.
3. Add lookups and relationships.
4. Configure ownership, security roles and auditing.
5. Add alternate keys where idempotent upsert is required.
6. Verify choice values and schema names in the target environment.

## 3. Create specialist agents

Create and publish specialist agents before connecting them to the orchestrator:
1. Research Specialist.
2. Persona Profiler.
3. Committee Facilitator.
4. Stakeholder Twin (role-conditioned; optionally duplicate as role-specific connected agents).
5. Sales Coach & MEDDPICC.
6. Scenario & Calibration Analyst.

For each agent:
- Select the standard Copilot Studio harness.
- Set English as primary language.
- Add the matching prompt from prompts/agent-prompts.md.
- Add only the Dataverse/knowledge/tools required for its task.
- Configure descriptions and input expectations.
- Test valid, missing, ambiguous and adversarial inputs.
- Publish the agent.

## 4. Create orchestrator

1. Create **Sales Digital Twins Orchestrator** using standard harness.
2. Add P00 instructions.
3. Enable generative orchestration.
4. Add connected specialist agents and Dataverse/agent flow tools.
5. Add the topics from topic-specifications.md.
6. Keep confirmation and approval steps explicit.
7. Configure Teams authentication.

## 5. Create agent flows

Create AF01–AF07 described in topic-specifications.md. For each flow:
- Use the agent-call trigger and response action when created as an agent flow tool.
- Define typed inputs and outputs.
- Add Dataverse actions using solution connection references.
- Validate required fields before writes.
- Persist flow correlation ID and status.
- Add scopes for try/catch/finally where supported.
- Return structured status and safe user-facing error.
- Publish the flow and add it as an orchestrator tool.

For AF04 simulation loop, enforce max 3 rounds and bounded retries. Persist each turn as soon as validated. Do not store complete transcript only in flow memory.

## 6. Configure Teams

1. Publish the orchestrator.
2. Open Channels and select Microsoft Teams.
3. Configure availability according to tenant policy.
4. Test with a pilot security group.
5. Verify Entra sign-in and Dataverse permissions for standard user and manager roles.
6. Obtain Teams admin approval and publish/distribute the app.

## 7. Test and release

Run all tests in acceptance-tests.md. Export the solution as managed for Test/Production. Import connection references and environment configuration, run smoke tests, publish agents/flows, then release to pilot group.

## 8. Operational readiness

- Assign product owner, platform owner and support owner.
- Monitor agent analytics and flow run history.
- Review failed simulations and invalid prompt outputs.
- Review usage/capacity and Dataverse storage.
- Version prompts and update release notes.
- Review feedback and calibration quality before expanding rollout.

## 9. Known implementation caveats

- Copilot Studio UI labels and feature availability can vary by tenant, region, license and harness.
- Agent flow loop, execution-duration and action limits must be validated in the target environment.
- This repository package does not contain a Power Platform solution export; actual platform objects must be created in the maker environment.
- If native agent-flow execution cannot complete within tenant limits, split the process into resumable flow stages while keeping the architecture within Power Platform.
