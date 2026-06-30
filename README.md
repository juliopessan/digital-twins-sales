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

## Rodando

```bash
pip install -r requirements.txt

# Sem chave de API — usa MockLLMClient, determinístico, valida o grafo:
python -m digital_twins.main --mock -v

# Com Claude de verdade:
export ANTHROPIC_API_KEY=sk-ant-...
python -m digital_twins.main -v

# Com uma conta real (JSON no shape de AccountContext):
python -m digital_twins.main --account minha_conta.json -v
```

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
