# Sales Digital Twins — Hierarchical Multi-Agent Stakeholder Debate

![Sales Digital Twins — results screen with the committee's clay/mint ledger](docs/screenshot-results.png)

A multi-agent Python system, hierarchically orchestrated via LangGraph,
that simulates debates between personas on a buying committee (CFO, CTO,
Procurement, Champion, etc.) to help sales reps stress-test a pitch,
anticipate objections, and calibrate their talk track before a real meeting.

## 🎬 "The Room"

Every B2B seller knows that room. It's where the biggest deal of the
quarter gets decided, with the CFO, the CTO, and Procurement on the other
side of the table — and one shot to convince them. The problem is that
committee exists to tear proposals apart: every number gets questioned,
every promise gets tested, and the seller almost always finds out where
their pitch had holes too late, after the "no" has already been said. The
real rehearsal happens at the wrong time, in front of the wrong people.

Sales Digital Twins was born from a simple question: what if you could
walk into that room before the room? Instead of discovering objections in
the actual meeting, the seller faces them beforehand — against a synthetic
buying committee that behaves like the real one. Each stakeholder is a
digital twin: when real account data exists (from LinkedIn, CRM, or
automatic research via EXA), the persona is grounded in those facts; when
it doesn't, it falls back to a curated archetype for that role. These
aren't generic stereotypes — they're personas anchored in real market
context.

And they don't go easy. The seller pastes their own opening pitch and the
committee reacts to their exact words — the CFO demands the numbers behind
a "payback in 3 months," the CTO attacks the integration, Procurement
demands a benchmark. All of it orchestrated by a Facilitator that decides
who speaks, when to escalate a blocking objection, and when the debate has
run its course — a real meeting-room dynamic, not isolated answers.

In the end, the product delivers what matters: an actionable verdict. A
MEDDPICC scorecard shows where the deal stands and where it's at risk;
and, when the seller tested their own pitch, a coach evaluates their
performance — what landed, what backfired, and exactly what to say next
time, with line-by-line rewrites. The seller walks back into the real room
with the posture of someone who's already been there.

That's the promise the product delivers on: **rehearse the worst committee
of your life, before it's real.**

---

Runs in **two modes**, on the same pipeline:

- **Deal war-gaming** (autonomous): the committee debates your proposal on
  its own and you read the report. "Before the call, see how the committee
  is going to tear your deal apart."
- **Training simulator** (with your own pitch): you paste your opening
  pitch, the personas react to your **real words**, and a **Coach**
  evaluates how the pitch held up and rewrites the weak lines.

## Core concept: real → archetype fallback

For each role on the committee (`AccountContext.roles_in_committee`):

- If `AccountContext.real_data[role]` has facts (from CRM, call
  transcripts, LinkedIn, email), the persona is built as `DataSource.REAL`,
  with those facts injected directly into the agent's system prompt.
- If there's no data, it automatically falls back to `DataSource.ARCHETYPE`
  — a generic persona curated in `digital_twins/personas/archetypes.py`.

This means the same pipeline works both for **generic training** (no real
data, every persona is an archetype) and for **real account intelligence**
(CFO grounded in real data, the rest archetypes) — with no need to switch
systems.

## Architecture (hierarchical)

```
START → start_round (Facilitator sets the speaking order)
            ↓
        persona_turn (one persona speaks at a time, reacting to what's been said)
            ↓ (loop until everyone has spoken in the round)
        evaluate_round (Facilitator judges: continue / escalate / conclude)
            ↓
   ┌────────┴────────┐
   ↓ (continue/escalate)     ↓ (conclude)
 start_round (new round)     synthesize → END
```

The `Facilitator` is the supervisor: it decides speaking order and
whether the debate should continue, escalate (reorder to give the final
word to the highest-veto stakeholder who raised a blocker), or conclude.
The personas have no orchestration logic — they only generate
in-character content.

## Seller's opening pitch + Coach (MEDDPICC)

The optional `AccountContext.seller_opening` field holds the **seller's
actual statement** (the pitch as they'll really say it, in their own
words):

- **Blank** → the committee debates autonomously (war-gaming), reacting
  only to the abstract `pitch_summary`. Default behavior, unchanged.
- **Filled in** → each persona reacts to the seller's **exact words**, and
  the Synthesizer becomes a **Coach**: besides the committee's verdict, it
  evaluates the seller's performance (`DebateVerdict.seller_coaching`) —
  pitch grade, what landed, what backfired, and concrete line-by-line
  rewrites ("instead of X, say Y because Z").

In both modes, the verdict also carries a **MEDDPICC scorecard**
(`DebateVerdict.meddpicc_scorecard`) covering the dimensions the debate
revealed (Metrics, Economic Buyer, Identify Pain, Champion). All of this
is additive: without `seller_opening`, the Synthesizer's prompt is
byte-for-byte the usual one and `seller_coaching` stays `None`.

## Status

✅ **Web UI (Next.js + FastAPI)** — the primary frontend, in `web/` +
`api/`, with its own design system ("Ledger") applied to the report: the
clay/mint pair visually distinguishes what was **measured** (committee
count, grounded personas, duration, number of LLM calls) from what was
**generated by the LLM** (objections, verdict, MEDDPICC scorecard).
- The backend (`api/main.py`) is a thin HTTP layer over the same
  `digital_twins/` engine — no debate logic was duplicated.
- The frontend (`web/`) consumes the API and runs the full flow: Setup →
  Run → Result (ledger, grounding callout, archetype flag, transcript,
  verdict, export).
- **Streamlit** (`streamlit_app.py`, `app_v2.py`) remains functional and is
  kept as the legacy UI — it includes the pixel-art Office Canvas, which
  hasn't been ported to Next.js yet.

## Local setup — Web UI (Next.js + FastAPI)

```bash
# 1. Backend: create the virtualenv and install dependencies
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure the Anthropic key (it's passed per request, never persisted)
cp .env.example .env
# edit .env and fill in ANTHROPIC_API_KEY=sk-ant-...

# 3. Start the API
uvicorn api.main:app --reload --port 8000

# 4. In another terminal, start the frontend
cd web
npm install
npm run dev
# opens at http://localhost:3000 — the API key can also be typed
# directly into the form (only kept in memory during the run)
```

## Local setup — Streamlit (legacy)

```bash
# 1. From the project folder, create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the dependencies (includes Streamlit and the EXA client)
pip install -r requirements.txt

# 3. Configure the Anthropic key (required — there's no mock mode anymore)
cp .env.example .env
# edit .env and fill in ANTHROPIC_API_KEY=sk-ant-...
# optional: EXA_API_KEY=... (automatic stakeholder research in Streamlit)
```

## CLI

```bash
# Needs ANTHROPIC_API_KEY (in .env or exported):
python -m digital_twins.main -v

# With a real account (JSON in the AccountContext shape, e.g. accounts/ifood.json):
python -m digital_twins.main --account accounts/ifood.json -v
```

Every run writes a `.md` report, an `.html` one (styled, see the section
below), and a `.json` snapshot (`SimulationRecord`, used by post-call
calibration) into `reports/`.

## What-if scenarios ("branch, simulate, compare")

Instead of a single debate, declare N deal variants (price A vs. B,
with/without a POC, anchor on ROI vs. risk) in a JSON file — each one is a
"branch" of the base `AccountContext` that only carries the delta — and
run them all at once:

```bash
python -m digital_twins.main --scenarios accounts/cenarios_exemplo.json
```

This produces a side-by-side comparison in
`reports/<account>-scenarios-<ts>.md`, ranked by an aggregate risk score
(overall sentiment + number of blockers + lack of consensus), with the
recommended scenario at the top.

## Post-call calibration (twin vs. reality)

After the real call happens, compare what the twin PREDICTED against what
was actually said:

```bash
python -m digital_twins.calibration \
  --simulation reports/<account>-<ts>.json \
  --call-transcript call.txt \
  --out reports/calibration.md
```

The report shows: per-persona fidelity (predicted objections that
actually came up), blind spots (real objections that weren't predicted),
and concrete suggestions for facts to add to `AccountContext.real_data` —
closing the twin's continuous-improvement loop.

## Streamlit interface

```bash
streamlit run streamlit_app.py
```

Opens automatically at **http://localhost:8501**. To stop the server,
`Ctrl+C` in the terminal.

UI with proprietary design tokens (palette, typography, hero/arc/roadmap
components).

### Meeting room (Office canvas — squad-pod Canvas 2D engine)

`digital_twins/office.py` is an adaptation of the Canvas 2D engine from
[swigerb/squad-pod](https://github.com/swigerb/squad-pod) (a VS Code
extension) for Streamlit via `st.html()`. The engine is fully self-contained
HTML/JS embedded in Python — no external image dependencies.

**Engine architecture (squad-pod style):**

| Component | Detail |
|---|---|
| **Grid** | `TILE=16px`, `ZOOM=3×` → `TS=48px` per on-screen tile |
| **Sprites** | 16×24 px, generated pixel-by-pixel in JS: 4 walking frames + 2 typing frames, 6 color palettes (shirt/skin/pants) |
| **Speech bubbles** | 12×10 pixel-art arrays (`?` = waiting · `...` = typing), with alpha fade |
| **Pathfinding** | BFS over the `tileMap` — each character walks to their desk on start, avoiding `WALL`/`DESK`/`VOID` |
| **Z-sort** | Desks + characters share a `Drawable[]`, sorted by `bottomY` every frame (squad-pod pattern) |
| **State machine** | `walk → idle → type → done/error`; `done` adds spark particles; `error` shows a pulsing red overlay |
| **Desks** | Textured wood top, monitor with active/inactive cyan screen, pixel-art keyboard |
| **Loop** | Continuous `requestAnimationFrame`; resize reinitializes the canvas |

The Python thread injects `STATES`, `AGENTS`, and `LAYOUT` as JSON; the JS
reads each agent's status every frame and transitions the characters
automatically. The ambient animation plays client-side while the backend
processes; the final states (`done`/`error`) appear on the post-LangGraph
rerender.

In the sidebar you can pick the account (a sample account, any file in
`accounts/`, **manual entry** of a company + real stakeholder, or upload a
custom JSON), optionally paste **your opening pitch** (activates training
mode + Coach), provide the Anthropic key (required, typed into the
session, never saved to disk), and adjust the maximum number of rounds.
At the end, the result shows the committee, the animated meeting room,
objections, action plan, risk assessment, the MEDDPICC scorecard, and — if
you pasted your pitch — the Coach's evaluation; plus two download buttons:
a simple `.md` report and a styled `.html` report, ready to send to the
sales team.

### Automatic stakeholder research (EXA)

In the "Enter manually" form, instead of typing in known facts about the
real stakeholder by hand, you can provide an **EXA API key** (optional)
and click "🔎 Research facts with EXA" — `digital_twins/research.py` uses
Exa's Answer API to pull public, specific, cited facts about the person
(the same kind of research done manually for the iFood test account, now
automated).

## Tests

```bash
pytest tests/ -v
```

`PersonaFactory` tests always run (no LLM involved). The full-graph test
(`test_full_graph_runs_end_to_end_with_real_client`) needs
`ANTHROPIC_API_KEY` configured — there's no mock in the project, so it's
skipped automatically if the key isn't present.

## Model per layer (cost)

Configurable via env (`digital_twins/config.py`) — everything uses
**Haiku 4.5** by default to reduce cost:

- `DT_PERSONA_MODEL` — each persona's statements (high volume). Default: `claude-haiku-4-5-20251001`.
- `DT_FACILITATOR_MODEL` / `DT_SYNTHESIZER_MODEL` — convergence judgment
  and final synthesis. Default: `claude-haiku-4-5-20251001` (swap to
  `claude-sonnet-5` if you want higher quality on these two nodes).

## Language

The entire pipeline — UI, CLI, reports, and the prompts that generate the
personas' statements — runs in English. The only tokens that stay in
English by design are internal enum values used for code parsing (e.g.
the `SENTIMENT: supportive|neutral|skeptical|blocking` tag and the
`decision`/role values in the facilitator's and synthesizer's JSON) —
those never surface to the end user, they only flow between graph nodes.

**Translation safety net** (`digital_twins/i18n.py`): even with prompts in
English, LLMs occasionally slip into another language in short snippets.
`to_en()`/`to_en_list()` detect the language (`langdetect`) and
automatically translate (`deep-translator`/Google Translate) any persona
statement, objection, talk-track item, or risk summary that isn't in
English — applied in `persona_agent.py` and `synthesizer.py`. It fails
safe: if detection/translation errors out (no network, text too short),
the original text is kept instead of breaking the debate.

## Evolution roadmap (5 agents)

Mapped against the conceptual 5-agent architecture of a synthetic-persona
system:

| # | Conceptual agent | Current implementation | Status |
|---|---|---|---|
| 1 | Data Harvester | `research.py` (EXA Answer API) | Partial (manual form only) |
| 2 | Profiler | `PersonaFactory` + real/archetype fallback | ✅ |
| 3 | Digital Twin (Actor) | `persona_agent.py` (reacts to `seller_opening`) | ✅ |
| 4 | Moderator | `Facilitator` (hierarchical graph + escalation) | ✅ |
| 5 | Coach / Evaluator | `synthesizer.py` (MEDDPICC + `seller_coaching`) | ✅ |

- **Phase 1 (done)** — seller's opening pitch: personas react to real
  words.
- **Phase 2 (done)** — Coach evaluates the seller's pitch against the
  objections.
- **Phase 3 (backlog)** — turn-by-turn interactive mode: LangGraph's
  `interrupt()` + `MemorySaver` so the seller can respond each round, with
  replay and branching. **Changes the graph's topology** (from a single
  `invoke` to pausable execution), so it's a separate decision.

Other backlog items:

1. **Real-data connector**: extend EXA research (today only in the manual
   form) to also enrich accounts loaded via JSON, cross-referencing the
   stakeholder with the company's macro context.
2. **Governance guardrail**: when using `DataSource.REAL` over identifiable
   real people, define an explicit consent and data-retention policy
   before production (see `legal:compliance-check`).
3. **Evaluation**: an annotated debate dataset to measure whether generated
   objections match real objections collected post-call
   (objection precision/recall).

## 🎨 Web UI — Tabs & Office Canvas

```bash
streamlit run streamlit_app.py
# Opens at http://localhost:8501
```

### Tabs

| Tab | What you see | Action |
|-----|---|---|
| ⚙️ **Setup** | Account selector, opening pitch (optional), number of rounds, API key auto-load | Click "Run simulation" to start |
| 🎭 **Office Canvas** | Animated pixel-art meeting room — each persona at a desk, Facilitator walking between desks | Watch each stakeholder's status in real time (idle, working, done) |
| 📊 **Verdict** | MEDDPICC scorecard, convergence/divergence summary, per-persona objection list | Understand where the deal stands and where it fails |
| 🏆 **Coach** *(if a pitch was entered)* | Your pitch's performance review, line-by-line rewrites, areas to improve | Calibrate your talk track before the real call |
| 📥 **Export** | Download a simple `.md` report or a styled `.html` one (ready for email) | Share results with the sales team |

### 🎮 Office Canvas — Meeting Room in Real Time

`digital_twins/office.py` renders an **animated pixel-art canvas** where
each persona is a character at a desk:

#### Per-persona state machine

```
idle (seated, doing nothing)
  ↓ (LangGraph "start" event)
walk (leaves the desk, Facilitator walks over)
  ↓ (Facilitator arrives)
working (persona is thinking/speaking — LLM prompt running)
  ↓ (LLM response ready)
done (persona seated, with a green "done" bubble)
  ↓ (next round or end)
idle
```

#### Animation & rendering

- **60fps game loop** via `requestAnimationFrame` (client-side JavaScript)
- **2-pass rendering**: pass 1 draws all the background desks, pass 2 draws
  all the characters on top (keeps the Facilitator from being hidden when
  crossing cells)
- **The Facilitator walks "desk to desk"** synced to LangGraph `start`
  events — real-time speed, not pre-recorded (17px/frame ≈ 0.38s per desk,
  ~2.7s total for the whole group)
- **Speech bubbles** with themed one-liners per persona (25 humorous
  variations each; e.g. CFO → `"Payback in 3 months? From which planet?"`,
  CTO → `"Integration with our legacy stack? Good luck 😅"`)
- **Sparkle particles** when a persona finishes (status `done`)
- **Auto-height**: a `ResizeObserver` on the canvas reports its real height
  to the Streamlit iframe

#### Desk layout

- **Row 1**: Facilitator (supervisor, walks between everyone else)
- **Row 2**: Primary stakeholders (CFO, CTO, Procurement)
- **Row 3**: Secondary stakeholders (Champion, Compliance, etc.)
- **Row 4**: Synthesizer (final-consensus generator)

#### LangGraph integration

While the graph (`orchestration/graph.py`) executes:
1. Each node fires events via `node.stream(...)` on entry/exit
2. A background thread consumes those events (a thread-safe queue)
3. Streamlit rerun → the canvas renders the updated states
4. Once every node finishes, the canvas shows `done` in green for everyone

Result: **you follow the debate in real time** with no polling, and the
final state is deterministic (no race conditions).

### ⚙️ Sidebar — Round setup

- **Account** — Dropdown selector: accounts pre-loaded in `accounts/`, or a
  custom JSON upload
- **Account data** — Expander with metadata: Company, Pitch, Solution,
  Value, Committee (stakeholders)
- **Your opening pitch** — Optional text field: paste the pitch as you'll
  actually say it. If filled in, personas react to your real words + Coach
  evaluates performance
- **Anthropic API key** — **Auto-loaded from `.env`** if present (green
  badge: ✓ "API key loaded from environment variable"). If absent, an
  input field with a hint to use `.env`
- **Max rounds** — Slider 1–5 (controls how many rounds the debate can run)
- **"Run simulation" button** — Starts the LangGraph graph

### 📊 Verdict tab

Once the simulation finishes:

```
┌─────────────────────────────────────┐
│ MEDDPICC SCORECARD                  │
├─────────────────────────────────────┤
│ 🎯 Metrics          ✅ Strong       │
│ 💰 Economic Buyer   ⚠️  At risk     │
│ 💔 Identify Pain    ✅ Strong       │
│ 🏆 Champion         ⚠️  At risk     │
└─────────────────────────────────────┘

📍 Convergence: 71% (majority wants to move forward)
🚨 Blocking objections (2):
   - CFO: "Payback doesn't match our internal use case"
   - CTO: "Integration with legacy system, takes 6 months"
```

### 🏆 Coach tab *(conditional — only appears if you entered a pitch)*

If `AccountContext.seller_opening` was filled in, the Synthesizer
generates coaching:

```
📋 Pitch performance: 7.2/10

✨ What landed:
  - "Problem: manual integration" resonated with the CTO
  - "3 healthcare clients" gave credibility

❌ What didn't work:
  - "Payback in 3 months" was challenged 3 times
  - "No hidden cost" was met with skepticism

📝 Line-by-line rewrites:

Your line:      "Payback in 3 months, completely no hidden cost"
Coach suggests: "Payback in 12 months, including integration.
                 Full cost visible in the quote, approved by Procurement."
Reason:         The CFO expected realism; "no cost" is a red flag.

---

Your line:      "Fast integration with your infrastructure"
Coach suggests: "API-first integration with your stack.
                 The CTO will set the timeline based on complexity."
Reason:         The CTO needs technical control, not vague promises.
```

---

## 🔄 Feedback Loop — Immune System

Inspired by "Agents are 30% of the work. The other 70% is the immune
system."

Every finding/objection can be **approved** (`👍`) or **rejected** (`👎`):

### Feedback flow

1. **Saved** to `~/.digital-twins/feedback/<account>.json` (FIFO, max 100
   entries)
2. **Injected** into the prompt for the next simulation of the same
   account:
   ```
   ## Feedback from previous simulations (check BEFORE suggesting objections)

   ### ❌ REJECTED — do NOT suggest again:
     - [2026-07-01 14:30] "Integration takes 6 months"
       → Reason: We already integrated with this stack in 2 months (client Y)

   ### ✅ APPROVED — look for similar patterns:
     - [2026-07-01 14:00] "We don't have budget this year"
       → A legitimate CFO raised this; give it weight
   ```

3. **Routed** by context (a CFO rejection goes back into the CFO's prompt
   next round, etc.)

### Memory dashboard *(Future)*

A "🧠 Memory" tab (to be implemented) will show:

- Feedback loop stats per account
- Capacity per account (n/100)
- A "Clear feedback" reset button
- History of approved/rejected items over time

---

## 📦 Design tokens (legacy Streamlit UI)

The reports (`.md` and `.html`) generated by `streamlit_app.py`/`app_v2.py`
and the canvas use a proprietary design palette, defined as CSS custom
properties (`--dt-orange`, `--dt-aurora`, etc.) in
`digital_twins/reporting.py`:

| Element | Token | Color |
|----------|-------|-----|
| Primary | `--dt-orange` | `#FF5800` |
| Secondary | `--dt-aurora` | `#890078` |
| Success | `--dt-success` | `#107C10` |
| Warning | `--dt-warning` | `#FFB900` |
| Error | `--dt-error` | `#E81123` |
| Dark mode | `@media (prefers-color-scheme: dark)` | Gold + gray scale |

The **Web UI (Next.js)**, by contrast, uses the Ledger design system —
warm paper, near-black ink, and the clay/mint pair reserved exclusively to
signal measured vs. generated data (see the "Status" section above and
`web/app/globals.css`).

Reports automatically adapt to the browser's theme (light/dark).
