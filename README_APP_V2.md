# Sales Digital Twins — UI/UX v2 with Navigation Bar

## 🎯 Objetivo

Refatoração completa da UI/UX seguindo o padrão **Microsoft Streamlit_UI_Template App 2** com:
- ✅ **Barra de navegação customizada** (`streamlit-navigation-bar`)
- ✅ **Estrutura modular** (pages/ directory)
- ✅ **Design System Avanade** (#FF5800, #890078, Segoe UI)
- ✅ **Tema dark/light** mantido
- ✅ **Canvas 2D em tempo real** funcionando

---

## 📦 Estrutura Modular

```
digital-twins-sales/
├── app_v2.py                 (main app com navegação)
├── streamlit_app.py          (versão anterior — mantida para referência)
├── pages/
│   ├── __init__.py
│   ├── setup.py              (🎯 Configuração)
│   ├── simulacao.py          (🎨 Canvas + Debate)
│   ├── veredito.py           (📋 Objeções + MEDDPICC)
│   ├── coach.py              (👔 Feedback do pitch)
│   └── export.py             (📤 Relatórios)
```

---

## 🚀 Como Rodar

```bash
# Via navegação (padrão App 2)
streamlit run app_v2.py

# Via versão anterior (legado)
streamlit run streamlit_app.py
```

Acesse: **http://localhost:8501**

---

## 🎨 Design System

### Paleta Avanade
- **Primário:** #FF5800 (Orange)
- **Secundário:** #890078 (Aurora)
- **Accent:** #FFD700 (Solar)
- **Texto:** #333333 (Grey-80)
- **Background:** #FFFFFF (White)

### Tipografia
- **Font:** Segoe UI
- **Nav:** 500 weight, 14px
- **Seções:** 600 weight, 19px
- **Body:** 400 weight, 14px

---

## 📄 Seções de Cada Página

### 🎯 Setup
- Seleção de conta (iFood, Nubank, Vale, etc)
- API Key da Anthropic
- Máximo de rounds (slider)
- Fala de abertura do seller (textarea)
- Botão: Rodar simulação

### 🎨 Simulação
- Canvas 2D com office (squad-pod engine)
- Agents navegando, digitando, transitando de estados
- Transcrição completa do debate
- Status em tempo real

### 📋 Veredito
- **Principais objeções** — tabela com stakeholder + objeção + sentimento
- **Bloqueadores & Contorno** — quem está bloqueando, estratégias de contorno
- **Busca de consenso** — métrica (%), próximos passos
- **MEDDPICC** — scorecard com 7 dimensões (Metrics, Economic Buyer, Decision Criteria, Decision Process, Pain, Identified Champion, Compelling Reason)
- **Plano de ação** — roadmap recomendado
- **Avaliação de risco** — 🟢🟡🔴 status

### 👔 Coach
- Nota geral do pitch (A–F)
- O que funcionou (pontos de aterramento)
- O que saiu pela culatra (armadilhas)
- Sugestões de reescrita (antes/depois)

### 📤 Export
- Markdown (.md)
- HTML (.html)
- JSON (.json)

---

## 🔄 Migrando Código da v1

Se você tem lógica em `streamlit_app.py` que quer mover para `app_v2.py`, siga este padrão:

### Original (streamlit_app.py)
```python
def render_office(personas, log):
    # ...
    st.html(office_html)
```

### Novo (pages/simulacao.py)
```python
def simulacao_page():
    # Importar e chamar render_office(personas, log)
    from digital_twins.office import render_office
    # ...
    st.html(office_html)
```

---

## ✅ Próximos Passos

1. **Integrar lógica de Setup**
   - Carregar accounts JSON
   - Validar API key
   - Salvar em session_state

2. **Integrar Simulação**
   - Rodar graph com app.stream()
   - Passar eventos para fila
   - Renderizar canvas em tempo real

3. **Integrar Veredito**
   - Renderizar objeções + blockers + consenso
   - MEDDPICC expandable
   - Roadmap com timelines

4. **Integrar Coach**
   - Avaliar fala de abertura
   - Gerar feedback estruturado

5. **Integrar Export**
   - Gerar Markdown
   - Gerar HTML
   - Gerar JSON

---

## 🛠️ Tecnologias

- **Streamlit 1.40.0** — Web UI framework
- **streamlit-navigation-bar** — Navigation component
- **LangGraph** — Multi-agent orchestration
- **Claude Haiku 4.5** — LLM (padrão)
- **Pydantic 2.12+** — Data validation
- **squad-pod engine** — Canvas 2D (self-contained)

---

## 📝 Commits Recentes

```
refactor: apply Microsoft App 2 UI pattern with modular pages
- Created pages/ directory structure
- Implemented st_navbar() with Avanade colors (#FF5800, #890078)
- Created placeholder pages: setup, simulacao, veredito, coach, export
- Added custom CSS with theme variables and navigation styling
- Installed streamlit-navigation-bar dependency
- Preserved all existing features (real-time rendering, theme toggle, favicon)
```

---

## 🔗 Referências

- [Microsoft Streamlit_UI_Template](https://github.com/microsoft/Streamlit_UI_Template)
- [streamlit-navigation-bar Docs](https://github.com/Gabriel-Leao/streamlit-navigation-bar)
- [Streamlit Docs](https://docs.streamlit.io)

---

**Status:** ✅ MVP pronto — Pages estruturadas, navegação funcionando, placeholders em lugar. Próximo: migrar lógica v1 → v2.
