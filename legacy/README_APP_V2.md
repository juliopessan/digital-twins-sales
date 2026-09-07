# Sales Digital Twins — UI/UX v2 with Navigation Bar

## 🎯 Goal

Full UI/UX refactor following the **Microsoft Streamlit_UI_Template App 2** pattern, with:
- ✅ **Custom navigation bar** (`streamlit-navigation-bar`)
- ✅ **Modular structure** (pages/ directory)
- ✅ **Proprietary design palette** (#FF5800, #890078, Segoe UI)
- ✅ **Dark/light theme** preserved
- ✅ **Real-time 2D canvas** working

---

## 📦 Modular structure

```
digital-twins-sales/
├── app_v2.py                 (main app with navigation)
├── streamlit_app.py          (previous version — kept for reference)
├── pages/
│   ├── __init__.py
│   ├── setup.py              (🎯 Setup)
│   ├── simulation.py         (🎨 Canvas + Debate)
│   ├── verdict.py            (📋 Objections + MEDDPICC)
│   ├── coach.py              (👔 Pitch feedback)
│   └── export.py             (📤 Reports)
```

---

## 🚀 How to run

```bash
# Via navigation (App 2 pattern)
streamlit run app_v2.py

# Via the previous version (legacy)
streamlit run streamlit_app.py
```

Open: **http://localhost:8501**

---

## 🎨 Design System

### Color palette
- **Primary:** #FF5800 (Orange)
- **Secondary:** #890078 (Aurora)
- **Accent:** #FFD700 (Solar)
- **Text:** #333333 (Grey-80)
- **Background:** #FFFFFF (White)

### Typography
- **Font:** Segoe UI
- **Nav:** 500 weight, 14px
- **Sections:** 600 weight, 19px
- **Body:** 400 weight, 14px

---

## 📄 Sections of each page

### 🎯 Setup
- Account selection (iFood, Nubank, Vale, etc.)
- Anthropic API key
- Max rounds (slider)
- Seller's opening statement (textarea)
- Button: Run simulation

### 🎨 Simulation
- 2D canvas with the office (squad-pod engine)
- Agents walking, typing, transitioning between states
- Full debate transcript
- Real-time status

### 📋 Verdict
- **Top objections** — table with stakeholder + objection + sentiment
- **Blockers & workarounds** — who's blocking, workaround strategies
- **Consensus tracking** — metric (%), next steps
- **MEDDPICC** — scorecard with 7 dimensions (Metrics, Economic Buyer, Decision Criteria, Decision Process, Pain, Identified Champion, Compelling Reason)
- **Action plan** — recommended roadmap
- **Risk assessment** — 🟢🟡🔴 status

### 👔 Coach
- Overall pitch grade (A–F)
- What landed
- What backfired (pitfalls)
- Rewrite suggestions (before/after)

### 📤 Export
- Markdown (.md)
- HTML (.html)
- JSON (.json)

---

## 🔄 Migrating code from v1

If you have logic in `streamlit_app.py` that you want to move to `app_v2.py`, follow this pattern:

### Original (streamlit_app.py)
```python
def render_office(personas, log):
    # ...
    st.html(office_html)
```

### New (pages/simulation.py)
```python
def simulation_page():
    # Import and call render_office(personas, log)
    from digital_twins.office import render_office
    # ...
    st.html(office_html)
```

---

## ✅ Next steps

1. **Integrate Setup logic**
   - Load accounts JSON
   - Validate the API key
   - Save to session_state

2. **Integrate Simulation**
   - Run the graph with app.stream()
   - Push events to a queue
   - Render the canvas in real time

3. **Integrate Verdict**
   - Render objections + blockers + consensus
   - Expandable MEDDPICC
   - Roadmap with timelines

4. **Integrate Coach**
   - Evaluate the opening statement
   - Generate structured feedback

5. **Integrate Export**
   - Generate Markdown
   - Generate HTML
   - Generate JSON

---

## 🛠️ Technologies

- **Streamlit 1.40.0** — Web UI framework
- **streamlit-navigation-bar** — Navigation component
- **LangGraph** — Multi-agent orchestration
- **Claude Haiku 4.5** — LLM (default)
- **Pydantic 2.12+** — Data validation
- **squad-pod engine** — 2D Canvas (self-contained)

---

## 📝 Recent commits

```
refactor: apply Microsoft App 2 UI pattern with modular pages
- Created pages/ directory structure
- Implemented st_navbar() with the custom brand colors (#FF5800, #890078)
- Created placeholder pages: setup, simulation, verdict, coach, export
- Added custom CSS with theme variables and navigation styling
- Installed streamlit-navigation-bar dependency
- Preserved all existing features (real-time rendering, theme toggle, favicon)
```

---

## 🔗 References

- [Microsoft Streamlit_UI_Template](https://github.com/microsoft/Streamlit_UI_Template)
- [streamlit-navigation-bar Docs](https://github.com/Gabriel-Leao/streamlit-navigation-bar)
- [Streamlit Docs](https://docs.streamlit.io)

---

**Status:** ✅ MVP ready — pages structured, navigation working, placeholders in place. Next: migrate v1 logic → v2.

### AI-assisted pitch generation

In the sidebar, next to **Your opening statement (optional)**, use the **✨** icon to generate a pitch suggestion contextualized to the selected account. Review the text before starting the simulation. This feature requires a valid `ANTHROPIC_API_KEY`.

---

## Tabs (streamlit_app.py / app_v2.py)

| Tab | What you see | Action |
|-----|---|---|
| ⚙️ **Setup** | Account selector, opening pitch (optional), number of rounds, API key auto-load | Click "Run simulation" to start |
| 🎭 **Office Canvas** | Animated pixel-art meeting room — each persona at a desk, Facilitator walking between desks | Watch each stakeholder's status in real time (idle, working, done) |
| 📊 **Verdict** | MEDDPICC scorecard, convergence/divergence summary, per-persona objection list | Understand where the deal stands and where it fails |
| 🏆 **Coach** *(if a pitch was entered)* | Your pitch's performance review, line-by-line rewrites, areas to improve | Calibrate your talk track before the real call |
| 📥 **Export** | Download a simple `.md` report or a styled `.html` one (ready for email) | Share results with the sales team |

## 🎮 Office Canvas — Meeting Room in Real Time

`office.py` (in this same `legacy/` folder) renders an **animated
pixel-art canvas** where each persona is a character at a desk. It's an
adaptation of the Canvas 2D engine from
[swigerb/squad-pod](https://github.com/swigerb/squad-pod) (a VS Code
extension) for Streamlit via `st.html()`. The engine is fully
self-contained HTML/JS embedded in Python — no external image
dependencies.

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

While the graph (`digital_twins/orchestration/graph.py`) executes:
1. Each node fires events via `node.stream(...)` on entry/exit
2. A background thread consumes those events (a thread-safe queue)
3. Streamlit rerun → the canvas renders the updated states
4. Once every node finishes, the canvas shows `done` in green for everyone

Result: **you follow the debate in real time** with no polling, and the
final state is deterministic (no race conditions).

## Sidebar — Round setup

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

## Verdict tab

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

## Coach tab *(conditional — only appears if you entered a pitch)*

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

## Design tokens

This legacy UI's own screens (not the downloadable reports — those moved
to the Ledger design system, see the main `README.md`) use a proprietary
palette, defined as CSS custom properties (`--dt-orange`, `--dt-aurora`,
etc.) inline in `streamlit_app.py`/`app_v2.py`:

| Element | Token | Color |
|----------|-------|-----|
| Primary | `--dt-orange` | `#FF5800` |
| Secondary | `--dt-aurora` | `#890078` |
| Success | `--dt-success` | `#107C10` |
| Warning | `--dt-warning` | `#FFB900` |
| Error | `--dt-error` | `#E81123` |
| Dark mode | `@media (prefers-color-scheme: dark)` | Gold + gray scale |
