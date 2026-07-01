# Sales Digital Twins — Hierarchical Multi-Agent Stakeholder Debate

Sistema multiagente em Python, orquestrado hierarquicamente via LangGraph,
que simula debates entre personas de um comitê de compra (CFO, CTO,
Procurement, Champion, etc.) para apoiar o time de vendas a testar pitch,
antecipar objeções e calibrar talk track antes de uma reunião real.

Roda em **dois modos**, com o mesmo pipeline:

- **War-gaming de deal** (autônomo): o comitê debate sozinho a sua proposta
  e você lê o relatório. "Antes da call, veja como o comitê vai despedaçar
  seu deal."
- **Simulador de treino** (com a sua fala): você cola o seu pitch de
  abertura, as personas reagem às suas **palavras reais**, e um **Coach**
  avalia como o pitch se sustentou e reescreve as falas fracas.

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

## Pitch de abertura do vendedor + Coach (MEDDPICC)

O campo opcional `AccountContext.seller_opening` guarda a **fala real do
vendedor** (o pitch como ele vai dizer, com as palavras dele):

- **Em branco** → o comitê debate de forma autônoma (war-gaming), reagindo
  apenas ao `pitch_summary` abstrato. Comportamento padrão, inalterado.
- **Preenchido** → cada persona reage às **palavras exatas** do vendedor, e
  o Synthesizer vira um **Coach**: além do veredito do comitê, avalia o
  desempenho do vendedor (`DebateVerdict.seller_coaching`) — nota do pitch,
  o que ressoou, o que saiu pela culatra, e reescritas concretas linha a
  linha ("em vez de X, diga Y porque Z").

Em ambos os modos, o veredito também traz um **scorecard MEDDPICC**
(`DebateVerdict.meddpicc_scorecard`) com as dimensões que o debate revelou
(Metrics, Economic Buyer, Identify Pain, Champion). Tudo isso é aditivo: sem
`seller_opening`, o prompt do Synthesizer é byte-a-byte o de sempre e o
`seller_coaching` fica `None`.

## Status

✅ **Streamlit app running** — Interface fully functional at http://localhost:8501.  
- Fixed Streamlit 1.40.0 compatibility: `st.iframe()` → `st.html()` (committee view + debate transcript).
- All personas render correctly with veto scores and stakeholder information.
- Ready for testing: select account, configure committee, run simulation.

## Setup local (terminal)

```bash
# 1. Dentro da pasta do projeto, crie e ative um virtualenv
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Instale as dependências (inclui o Streamlit e o cliente EXA)
pip install -r requirements.txt

# 3. Configure a chave da Anthropic (obrigatória — não há mais modo mock)
cp .env.example .env
# edite o .env e preencha ANTHROPIC_API_KEY=sk-ant-...
# opcional: EXA_API_KEY=... (pesquisa automática de stakeholder no Streamlit)
```

## CLI

```bash
# Precisa de ANTHROPIC_API_KEY (no .env ou exportada):
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
arquivo em `accounts/`, **digitar manualmente** empresa + stakeholder real,
ou upload de um JSON customizado), colar opcionalmente a **sua fala de
abertura** (ativa o modo treino + Coach), informar a chave Anthropic
(obrigatória, digitada na sessão, nunca salva em disco), e ajustar o número
máximo de rounds. Ao final, o resultado mostra o comitê, a sala de reunião
animada, objeções, plano de ação, avaliação de risco, o scorecard MEDDPICC
e — se você colou seu pitch — a avaliação do Coach; mais dois botões de
download: relatório `.md` simples e relatório `.html` estilizado (Avanade),
prontos pra enviar pro time de vendas.

### Pesquisa automática de stakeholder (EXA)

No formulário "Digitar manualmente", em vez de digitar à mão os fatos
conhecidos sobre o stakeholder real, dá pra informar uma **EXA API Key**
(opcional) e clicar em "🔎 Pesquisar fatos com EXA" — `digital_twins/research.py`
usa a Answer API da Exa para trazer fatos públicos, específicos e citados
sobre a pessoa (mesmo tipo de pesquisa feita manualmente para a conta de
teste do iFood, agora automatizada).

## Testes

```bash
pytest tests/ -v
```

Os testes de `PersonaFactory` rodam sempre (não usam LLM). O teste do
grafo completo (`test_full_graph_runs_end_to_end_with_real_client`) precisa
de `ANTHROPIC_API_KEY` configurada — sem mock no projeto, ele é pulado
automaticamente se a chave não estiver presente.

## Modelo por camada (custo)

Configurável via env (`digital_twins/config.py`) — tudo usa **Haiku 4.5**
por padrão para reduzir custo:

- `DT_PERSONA_MODEL` — falas de cada persona (volume alto). Default: `claude-haiku-4-5-20251001`.
- `DT_FACILITATOR_MODEL` / `DT_SYNTHESIZER_MODEL` — julgamento de
  convergência e síntese final. Default: `claude-haiku-4-5-20251001` (troque
  para `claude-sonnet-5` se quiser mais qualidade nesses dois nós).

## Idioma

Todo o pipeline — UI, CLI, relatórios e os prompts que geram a fala das
personas — está em português do Brasil. Os únicos tokens que permanecem em
inglês são valores de enum internos usados para parsing de código (ex: a
tag `SENTIMENT: supportive|neutral|skeptical|blocking` e os campos
`decision`/role values no JSON do facilitador e do sintetizador) — eles
nunca aparecem para o usuário final, só circulam entre os nós do grafo.

**Rede de segurança de tradução** (`digital_twins/i18n.py`): mesmo com os
prompts em português, LLMs ocasionalmente escorregam para o inglês em
trechos curtos. `to_pt_br()`/`to_pt_br_list()` detectam o idioma
(`langdetect`) e traduzem automaticamente (`deep-translator`/Google
Translate) qualquer fala de persona, objeção, item de talk track ou resumo
de risco que não esteja em português — aplicado em `persona_agent.py` e
`synthesizer.py`. Falha de forma segura: se a detecção/tradução der erro
(sem rede, texto curto demais), o texto original é mantido em vez de
quebrar o debate.

## Roadmap de evolução (5 agentes)

Mapeado contra a arquitetura conceitual de 5 agentes de um sistema de
personas sintéticas:

| # | Agente conceitual | Implementação atual | Status |
|---|---|---|---|
| 1 | Data Harvester | `research.py` (EXA Answer API) | Parcial (só no form manual) |
| 2 | Profiler | `PersonaFactory` + fallback real/arquétipo | ✅ |
| 3 | Digital Twin (Actor) | `persona_agent.py` (reage ao `seller_opening`) | ✅ |
| 4 | Moderator | `Facilitator` (grafo hierárquico + escalada) | ✅ |
| 5 | Coach / Avaliador | `synthesizer.py` (MEDDPICC + `seller_coaching`) | ✅ |

- **Fase 1 (feita)** — pitch de abertura do vendedor: personas reagem às
  palavras reais.
- **Fase 2 (feita)** — Coach avalia o pitch do vendedor contra as objeções.
- **Fase 3 (backlog)** — modo interativo turno-a-turno: `interrupt()` +
  `MemorySaver` do LangGraph para o vendedor responder a cada rodada, com
  replay e branching. **Muda a topologia do grafo** (de `invoke` único para
  execução pausável), então é uma decisão à parte.

Outros itens de backlog:

1. **Conector de dados reais**: expandir a pesquisa EXA (hoje só no
   formulário manual) para enriquecer também contas carregadas via JSON,
   cruzando o stakeholder com o contexto macro da empresa.
2. **Guardrail de governança**: ao usar `DataSource.REAL` sobre pessoas
   reais identificáveis, definir política explícita de consentimento e
   retenção de dados antes de produção (ver `legal:compliance-check`).
3. **Avaliação**: dataset de debates anotados para medir se as objeções
   geradas batem com objeções reais coletadas pós-call (precision/recall
   de objeção).

## 🎬 "A Sala" · Digital Twins Sales

Todo vendedor B2B conhece aquela sala. É onde o maior negócio do trimestre
vai ser decidido, com o CFO, o CTO e Compras do outro lado da mesa — e uma
única chance de convencê-los. O problema é que esse comitê existe para
despedaçar propostas: cada número é questionado, cada promessa é testada, e
o vendedor quase sempre descobre onde seu pitch tinha furos tarde demais,
quando o "não" já foi dado. O ensaio real acontece na hora errada, na frente
das pessoas erradas.

O Digital Twins Sales nasce de uma pergunta simples: e se você pudesse
entrar nessa sala antes da sala? Em vez de descobrir as objeções na reunião,
o vendedor as enfrenta antes — contra um comitê de compra sintético que se
comporta como o real. Cada stakeholder é um gêmeo digital: quando há dados
reais da conta (de LinkedIn, CRM ou de uma pesquisa automática via EXA), a
persona é embasada nesses fatos; quando não há, ela cai para um arquétipo
curado do papel. Não são estereótipos genéricos, e sim personas ancoradas no
contexto real de mercado.

E elas não pegam leve. O vendedor cola o próprio pitch de abertura e o
comitê reage às palavras exatas dele — o CFO cobra os números por trás de um
"payback em 3 meses", o CTO ataca a integração, Compras exige benchmark.
Tudo orquestrado por um Facilitador que decide quem fala, quando escalar uma
objeção bloqueadora e quando o debate chegou ao fim — uma dinâmica de sala de
reunião de verdade, não respostas isoladas. E o vendedor acompanha isso numa
sala de reunião animada, vendo o debate ganhar forma em tempo real.

No fim, o produto entrega o que importa: um veredito acionável. Um scorecard
MEDDPICC mostra onde o deal está de pé e onde está em risco; e, quando o
vendedor testou o próprio pitch, um coach avalia o desempenho dele — o que
ressoou, o que saiu pela culatra e exatamente o que dizer da próxima vez,
com reescritas linha a linha. O vendedor volta para a sala real com a
postura de quem já esteve lá.

É essa a promessa que o produto entrega: **ensaie o pior comitê da sua vida,
antes que ele seja real.** Digital Twins Sales — *Do what matters.*
