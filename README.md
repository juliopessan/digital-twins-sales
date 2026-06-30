# Sales Digital Twins — Hierarchical Multi-Agent Stakeholder Debate

MVP de um sistema multiagente em Python, orquestrado hierarquicamente via
LangGraph, que simula debates entre personas de um comitê de compra
(CFO, CTO, Procurement, Champion, etc.) para apoiar o time de vendas a
testar pitch, antecipar objeções e calibrar talk track antes de uma
reunião real.

## Conceito chave: fallback real → arquétipo

Para cada papel no comitê (`AccountContext.roles_in_committee`):

- Se `AccountContext.real_data[role]` tiver fatos (de CRM, transcrição de
  call, LinkedIn, e-mail), a persona é construída como `DataSource.REAL`,
  com esses fatos injetados diretamente no system prompt do agente.
- Se não houver dados, cai automaticamente para `DataSource.ARCHETYPE` —
  uma persona genérica curada em `digital_twins/personas/archetypes.py`.

Isso significa que o mesmo pipeline funciona tanto para **treino genérico**
(nenhum dado real, todas as personas são arquétipos) quanto para
**inteligência de conta real** (CFO grounded em dados reais, resto
arquétipo) — sem precisar trocar de sistema.

## Arquitetura (hierárquica)

```
START → start_round (Facilitator define ordem de fala)
            ↓
        persona_turn (uma persona fala por vez, reagindo ao que já foi dito)
            ↓ (loop até todos falarem na rodada)
        evaluate_round (Facilitator julga: continue / escalate / conclude)
            ↓
   ┌────────┴────────┐
   ↓ (continue/escalate)     ↓ (conclude)
 start_round (nova rodada)   synthesize → END
```

O `Facilitator` é o supervisor: decide ordem de fala e se o debate deve
continuar, escalar (reordenar para dar a palavra final ao stakeholder de
maior poder de veto que levantou um bloqueio) ou concluir. As personas não
têm lógica de orquestração — só geram conteúdo de personagem.

## Setup local (terminal)

```bash
# 1. Dentro da pasta do projeto, crie e ative um virtualenv
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Instale as dependências (inclui o Streamlit)
pip install -r requirements.txt

# 3. (Opcional, só se for rodar com Claude de verdade) configure a chave
cp .env.example .env
# edite o .env e preencha ANTHROPIC_API_KEY=sk-ant-...
```

Sem o passo 3, tudo funciona em **modo mock** (determinístico, sem custo de
API) — tanto na CLI (`--mock`) quanto no Streamlit (checkbox "Modo mock"
já vem marcado por padrão).

## CLI

```bash
# Sem chave de API — usa MockLLMClient, determinístico, valida o grafo:
python -m digital_twins.main --mock -v

# Com Claude de verdade (precisa do .env ou export ANTHROPIC_API_KEY=sk-ant-...):
python -m digital_twins.main -v

# Com uma conta real (JSON no shape de AccountContext, ex: accounts/ifood.json):
python -m digital_twins.main --account accounts/ifood.json -v
```

Cada run grava um relatório em `.md` e um em `.html` (estilizado, ver
seção abaixo) dentro de `reports/`.

## Interface Streamlit

```bash
streamlit run streamlit_app.py
```

Abre automaticamente em **http://localhost:8501**. Pra parar o servidor,
`Ctrl+C` no terminal.

UI com tokens de design Avanade Style Guide (paleta, tipografia, componentes
hero/arc/roadmap).

### Sala de reunião (Office canvas)

`digital_twins/office.py` é um port generalizado do **Squad Office** de
[juliopessan/arch-review-assistant](https://github.com/juliopessan/arch-review-assistant)
(`web/squad_office.py`): mesmo motor de canvas pixel-art (sprites, mesas,
balões de fala, máquina de estados `idle → walk → working → done`),
adaptado para um número arbitrário de personas em vez do squad fixo de 9
agentes — o Facilitador entra como o personagem que "anda mesa a mesa" (o
papel do Agent Manager lá), e o Sintetizador ganha sua própria mesa.

Mesma lógica de workflow da aba Squad Office: uma thread em background
roda o grafo LangGraph via `app.stream(...)` e empurra eventos
`start`/`done` por nó numa fila; a thread principal do Streamlit consome
essa fila dentro de um `st.spinner`, e um `st.rerun()` ao final garante
que o canvas mostre os estados finais corretos por persona. A animação
ambiente (idle/caminhada) toca client-side via JS enquanto o backend
processa; os estados precisos (`done`/`error`) só aparecem no rerender
pós-conclusão.

Na barra lateral dá pra escolher a conta (exemplo Northwind, qualquer
arquivo em `accounts/`, ou upload de um JSON customizado), alternar entre
modo mock e chave Anthropic real (digitada na sessão, nunca salva em
disco), e ajustar o número máximo de rounds. Ao final, dois botões de
download: relatório `.md` simples e relatório `.html` estilizado
(Avanade), prontos pra enviar pro time de vendas.

## Testes

```bash
pytest tests/ -v
```

## Modelo por camada (custo)

Configurável via env (`digital_twins/config.py`):

- `DT_PERSONA_MODEL` — modelo barato/rápido para as falas de cada persona
  (volume alto). Default: `claude-haiku-4-5-20251001`.
- `DT_FACILITATOR_MODEL` / `DT_SYNTHESIZER_MODEL` — modelo mais forte para
  julgamento de convergência e síntese final. Default: `claude-sonnet-5`.

## Próximos passos (backlog sugerido)

1. **Conector de dados reais**: popular `AccountContext.real_data` a partir
   de CRM/Gmail/LinkedIn automaticamente (hoje é manual ou via JSON).
2. **Persistência de sessão**: LangGraph suporta checkpointers nativos —
   plugar um (SQLite/Postgres) para retomar debates e fazer replay.
3. **Guardrail de governança**: ao usar `DataSource.REAL` sobre pessoas
   reais identificáveis, definir política explícita de consentimento e
   retenção de dados antes de produção (ver `legal:compliance-check`).
4. **Streaming**: expor `app.stream(...)` em vez de `app.invoke(...)` para
   o vendedor acompanhar o debate em tempo real em uma UI.
5. **Avaliação**: dataset de debates anotados para medir se as objeções
   geradas batem com objeções reais coletadas pós-call (precision/recall
   de objeção).
