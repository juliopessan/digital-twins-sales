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
- **Office canvas upgraded** to squad-pod Canvas 2D engine: pixel-art sprites (16×24), BFS pathfinding, Z-sorted render loop, speech bubbles with alpha fade.
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

### Sala de reunião (Office canvas — squad-pod Canvas 2D engine)

`digital_twins/office.py` é uma adaptação do motor Canvas 2D do
[swigerb/squad-pod](https://github.com/swigerb/squad-pod) (VS Code extension)
para Streamlit via `st.html()`. O motor é completamente auto-contido em HTML/JS
embutido no Python — sem dependências de imagens externas.

**Arquitetura do motor (squad-pod style):**

| Componente | Detalhe |
|---|---|
| **Grid** | `TILE=16px`, `ZOOM=3×` → `TS=48px` por tile em tela |
| **Sprites** | 16×24 px, gerados pixel-a-pixel em JS: 4 frames de caminhada + 2 frames de digitação, 6 paletas de cor (camisa/pele/calça) |
| **Bolhas de fala** | Arrays pixel-art 12×10 (`?` = aguardando · `...` = digitando), com fade alpha |
| **Pathfinding** | BFS no `tileMap` — cada personagem caminha até sua mesa ao iniciar, evitando `WALL`/`DESK`/`VOID` |
| **Z-sort** | Mesas + personagens compartilham `Drawable[]`, ordenados por `bottomY` a cada frame (squad-pod pattern) |
| **Máquina de estados** | `walk → idle → type → done/error`; `done` adiciona partículas de faísca; `error` overlay vermelho pulsante |
| **Mesas** | Tampo de madeira com textura, monitor com tela ciano ativa/inativa, teclado pixel-art |
| **Loop** | `requestAnimationFrame` contínuo; resize reinicializa o canvas |

A thread Python injeta `STATES`, `AGENTS` e `LAYOUT` como JSON; o JS
lê o status de cada agente a cada frame e transiciona os personagens
automaticamente. A animação ambiente toca client-side enquanto o backend
processa; os estados finais (`done`/`error`) aparecem no rerender pós-LangGraph.

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

---

## 🎨 Web UI — Tabs & Office Canvas

```bash
streamlit run streamlit_app.py
# Opens at http://localhost:8501
```

### Abas (Tabs)

| Aba | O que você vê | Ação |
|-----|---|---|
| ⚙️ **Configuração** | Selector de conta, pitch de abertura (opcional), número de rounds, API Key auto-load | Clique "Rodar simulação" para iniciar |
| 🎭 **Office Canvas** | Sala de reunião animada pixel-art — cada persona em uma mesa, Facilitador caminhando entre mesas | Veja em tempo real o estado de cada stakeholder (idle, working, done) |
| 📊 **Veredito** | Scorecard MEDDPICC, resumo de convergência/divergência, lista de objeções por persona | Entenda onde o deal está de pé e onde falha |
| 🏆 **Coach** *(se pitch inserido)* | Avaliação de desempenho do seu pitch, reescritas linha a linha, áreas para melhoria | Calibre talk track antes da call real |
| 📥 **Exportar** | Download `.md` (relatório simples) ou `.html` (estilizado Avanade, pronto pra e-mail) | Compartilhe resultados com o time de vendas |

### 🎮 Office Canvas — Sala de Reunião em Tempo Real

`digital_twins/office.py` renderiza um **canvas pixel-art animado** onde cada persona é um personagem em uma mesa:

#### Máquina de Estados por Persona

```
idle (sentado, sem fazer nada)
  ↓ (evento "start" do LangGraph)
walk (sai da mesa, Facilitador caminha para chegar)
  ↓ (Facilitador chega)
working (persona pensa/fala — prompt do LLM rodando)
  ↓ (resposta LLM pronta)
done (persona sentada, com balão verde "concluído")
  ↓ (próxima rodada ou fim)
idle
```

#### Animação & Rendering

- **60fps game loop** via `requestAnimationFrame` (JavaScript lado cliente)
- **2-pass rendering**: pass 1 desenha todas as mesas de fundo (backgrounds), pass 2 desenha todos os personagens em cima (evita Facilitador ficar escondido quando cruza células)
- **Facilitador caminha "mesa a mesa"** sincronizado com eventos de `start` do LangGraph — velocidade real-time, não pré-gravada (17px/frame ≈ 0.38s por mesa, ~2.7s total para todo o grupo)
- **Balões de fala** com mensagens temáticas por persona (25 variações humorísticas cada; ex: CFO → `"Payback em 3 meses? De qual planeta?"`, CTO → `"Integração com nossa stack legada? Boa sorte 😅"`)
- **Sparkle particles** ao persona terminar (status `done`)
- **Auto-height**: `ResizeObserver` no canvas reporta altura real ao iframe do Streamlit

#### Layout de Mesas

- **Linha 1**: Facilitador (supervisor, caminha entre os outros)
- **Linha 2**: Stakeholders primários (CFO, CTO, Procurement)
- **Linha 3**: Stakeholders secundários (Champion, Compliance, etc.)
- **Linha 4**: Synthesizer (gerador de consenso final)

#### Integração com LangGraph

Enquanto o grafo (`orchestration/graph.py`) executa:
1. Cada nó dispara eventos via `node.stream(...)` de entrada/saída
2. Uma thread background consome esses eventos (fila thread-safe)
3. Streamlit rerun → canvas renderiza estados atualizados
4. Quando todos os nós terminam, canvas mostra `done` em verde para todos

Resultado: **você acompanha o debate em tempo real** sem polling, e o estado final é determinístico (não há race conditions).

### ⚙️ Sidebar — Configuração da Rodada

- **Conta** — Seletor dropdown: contas pré-carregadas em `accounts/`, ou upload JSON customizado
- **Dados da Conta** — Expander com metadados: Empresa, Pitch, Solução, Valor, Comitê (stakeholders)
- **Sua Fala de Abertura** — Campo texto (opcional): cole o pitch como você vai dizer. Se preenchido, personas reagem às suas palavras reais + Coach avalia performance
- **Anthropic API Key** — **Auto-carregada do `.env`** se presente (badge verde: ✓ "API Key carregada de variável de ambiente"). Se ausente, campo de entrada com dica de usar `.env`
- **Máximo de Rounds** — Slider 1–5 (controla quantas rodadas o debate pode ter)
- **Botão "Rodar simulação"** — Inicia o grafo LangGraph

### 📊 Aba Veredito

Após a simulação terminar:

```
┌─────────────────────────────────────┐
│ SCORECARD MEDDPICC                  │
├─────────────────────────────────────┤
│ 🎯 Metrics          ✅ Forte        │
│ 💰 Economic Buyer   ⚠️  Risco       │
│ 💔 Identify Pain    ✅ Forte        │
│ 🏆 Champion         ⚠️  Risco       │
└─────────────────────────────────────┘

📍 Convergência: 71% (maioria quer avanço)
🚨 Objeções Bloqueadoras (2):
   - CFO: "Payback não bate com caso de uso interno"
   - CTO: "Integração com sistema legado, demora 6 meses"
```

### 🏆 Aba Coach *(condicional — só aparece se você inseriu pitch)*

Se `AccountContext.seller_opening` foi preenchido, o Synthesizer gera coaching:

```
📋 Desempenho do Pitch: 7.2/10

✨ O que funcionou:
  - "Problema: integração manual" ressoou com CTO
  - "3 clientes da área de saúde" deu credibilidade

❌ O que não funcionou:
  - "Payback em 3 meses" foi contestado 3 vezes
  - "Sem custo hidden" foi recebido com ceticismo

📝 Reescritas (linha a linha):

Sua fala:        "Payback em 3 meses, totalmente sem custo hidden"
Sugestão Coach:  "Payback em 12 meses, incluindo integração. 
                  Custo total visível no quote, aprovado por Procurement."
Motivo:          CFO esperava realismo; "sem custo" é red flag.

---

Sua fala:        "Integração rápida com sua infraestrutura"
Sugestão Coach:  "Integração com seu stack via API-first. 
                  O CTO vai determinar timeline baseado na complexidade."
Motivo:          CTO precisa de controle técnico, não promessas vagas.
```

---

## 🔄 Feedback Loop — Sistema Imunológico

Inspirado em "Agents são 30% do trabalho. Os outros 70% é o sistema imunológico."

Cada finding/objeção pode ser **aprovado** (`👍`) ou **rejeitado** (`👎`):

### Fluxo de Feedback

1. **Salvo** em `~/.digital-twins/feedback/<account>.json` (FIFO, max 100 entradas)
2. **Injetado** no prompt da próxima simulação da mesma conta:
   ```
   ## Feedback de Simulações Anteriores (consulte ANTES de sugerir objeções)
   
   ### ❌ REJEITADAS — NÃO sugira novamente:
     - [2026-07-01 14:30] "Integração leva 6 meses" 
       → Motivo: Já integramos com esse stack em 2 meses (cliente Y)
   
   ### ✅ APROVADAS — procure por padrões similares:
     - [2026-07-01 14:00] "Não temos budget este ano" 
       → CFO legítimo mencionou isso; dê peso
   ```

3. **Roteado** por contexto (rejeição de CFO volta para prompt do CFO na próxima rodada, etc.)

### Dashboard de Memory *(Futuro)*

Aba "🧠 Memory" (a implementar) mostrará:

- Feedback loop stats por account
- Capacidade por account (n/100)
- Botão "Limpar feedback" para reset
- Histórico de approved/rejected ao longo do tempo

---

## 📦 Integração com Avanade Design Tokens

Todos os reports (`.md` e `.html`) e o canvas usam a paleta Avanade:

| Elemento | Token | Cor |
|----------|-------|-----|
| Primário | `--ava-orange` | `#FF5800` |
| Secundário | `--ava-aurora` | `#890078` |
| Success | `--ava-success` | `#107C10` |
| Warning | `--ava-warning` | `#FFB900` |
| Error | `--ava-error` | `#E81123` |
| Dark mode | `@media (prefers-color-scheme: dark)` | Gold + escala cinza |

Relatórios adaptam-se automaticamente ao tema do navegador (light/dark).
