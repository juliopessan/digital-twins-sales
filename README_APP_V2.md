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
