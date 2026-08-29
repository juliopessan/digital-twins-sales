"""
Sales Board Office — squad-pod Canvas 2D engine adapted for Streamlit.

Adapts swigerb/squad-pod's architecture:
  • Tile-based floor + wall grid  (TILE=16px, ZOOM=3 → 48px on screen)
  • Per-agent seat assignment on the tile grid
  • BFS pathfinding — characters walk to their seats on spawn and on activation
  • Z-sorted scene rendering: desks and characters depth-sorted by bottom Y
  • 16×24 character sprites with 4-frame walk + 2-frame typing animation
    (ported from squad-pod defaultCharacters.ts createCharacter* functions)
  • Pixel-art speech bubbles (waiting / working) rendered at zoom scale
  • Direction-aware walk animation (LEFT / RIGHT / DOWN)
  • Character state machine: spawn-walk → idle → walk-to-seat → type → done

Python API is identical to the previous implementation:
  build_agent_defs(personas)                        → list[dict]
  build_layout(n_personas)                          → (layout, ncols, nrows)
  build_agent_states(log, keys)                     → dict
  build_office_html(agent_defs, layout, ncols, nrows, agent_states) → str
"""
from __future__ import annotations

import json

from digital_twins.models import StakeholderProfile, StakeholderRole

ROLE_ICON = {
    StakeholderRole.SALESMAN: "🎤",  # Active speaker
    StakeholderRole.CEO: "👑",
    StakeholderRole.CTO: "💻",
    StakeholderRole.CFO: "💰",
    StakeholderRole.PROCUREMENT: "📋",
    StakeholderRole.CHAMPION: "🚀",
    StakeholderRole.END_USER: "🧑‍💼",
    StakeholderRole.LEGAL_COMPLIANCE: "⚖️",
    StakeholderRole.SECURITY: "🔒",
}

FACILITATOR_KEY = "facilitator"
SYNTHESIZER_KEY = "synthesizer"
NCOLS = 4

# Mirrors the JS engine constants below — needed Python-side so the Streamlit
# apps can size the components.html iframe correctly (st.html does NOT run
# JavaScript, so the canvas must live inside an iframe component with an
# explicit height).
_TILE, _ZOOM = 16, 3
_BORDER, _CELL_H = 2, 4
_LABEL_PAD = 28


def office_canvas_height(nrows: int) -> int:
    """Altura em px do canvas do office para `nrows` fileiras de layout."""
    g_rows = _BORDER * 2 + nrows * _CELL_H
    return g_rows * _TILE * _ZOOM + _LABEL_PAD + 16


def build_agent_defs(personas: list[StakeholderProfile]) -> list[dict]:
    defs = [{"key": FACILITATOR_KEY, "ic": "🎯", "nm": "Facilitador", "variant": 0}]
    for i, p in enumerate(personas):
        defs.append({"key": p.role.value, "ic": ROLE_ICON.get(p.role, "🧑"), "nm": p.name, "variant": (i + 1) % 6})
    defs.append({"key": SYNTHESIZER_KEY, "ic": "🧠", "nm": "Síntese", "variant": (len(personas) + 1) % 6})
    return defs


def build_layout(n_personas: int) -> tuple[list[list[int]], int, int]:
    """[startCol, endCol, row, agentIdx] — facilitator on row 0, personas wrap
    across NCOLS-wide rows, synthesizer centered on the final row."""
    layout = [[1, 2, 0, 0]]  # facilitator, centered, row 0
    row, col = 1, 0
    for i in range(n_personas):
        layout.append([col, col, row, i + 1])
        col += 1
        if col >= NCOLS:
            col = 0
            row += 1
    if col != 0:
        row += 1
    layout.append([1, 2, row, n_personas + 1])  # synthesizer, centered, last row
    return layout, NCOLS, row + 1


def build_agent_states(log: list[dict], keys: list[str]) -> dict:
    # Um erro global (agent fora de `keys`, ex: "squad") derruba quem estava
    # rodando — sem isso o boneco fica digitando para sempre após uma falha.
    global_error = any(e["event"] == "error" and e.get("agent") not in keys for e in log)
    states = {}
    for key in keys:
        evts = [e for e in log if e.get("agent") == key]
        if any(e["event"] == "error" for e in evts) or (
            global_error and any(e["event"] == "start" for e in evts)
            and not any(e["event"] == "done" for e in evts)
        ):
            states[key] = {"status": "error", "count": 0}
        elif any(e["event"] == "done" for e in evts):
            states[key] = {"status": "done", "count": sum(1 for e in evts if e["event"] == "done")}
        elif any(e["event"] == "start" for e in evts):
            states[key] = {"status": "running", "count": 0}
        else:
            states[key] = {"status": "idle", "count": 0}
    return states


# ---------------------------------------------------------------------------
# HTML / Canvas builder
# ---------------------------------------------------------------------------

def build_office_html(
    agent_defs: list[dict],
    layout: list[list[int]],
    ncols: int,
    nrows: int,
    agent_states: dict,
    facilitator_label: str = "Facilitador",
) -> str:
    agents_json = json.dumps(agent_defs)
    layout_json = json.dumps(layout)
    states_json = json.dumps(agent_states)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@400..700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#1a1628;overflow:hidden;font-family:'Pixelify Sans',-apple-system,'Segoe UI',sans-serif}}
#wrap{{width:100%;position:relative}}
canvas{{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges}}
</style></head>
<body>
<div id="wrap"><canvas id="cv"></canvas></div>
<script>
// ── Data from Python ─────────────────────────────────────────────────────────
const STATES  = {states_json};
const AGENTS  = {agents_json};
const LAYOUT  = {layout_json};
const NCOLS_L = {ncols};
const NROWS_L = {nrows};
const FAC_KEY = "{FACILITATOR_KEY}";
const SYN_KEY = "{SYNTHESIZER_KEY}";

// ── Engine constants (squad-pod style) ───────────────────────────────────────
const TILE = 16;        // logical px per tile
const ZOOM = 3;         // display scale factor
const TS   = TILE * ZOOM; // screen px per tile (48)

// Tile types
const T_VOID  = 0;
const T_FLOOR = 1;
const T_WALL  = 2;
const T_DESK  = 3;   // blocked by desk furniture
const T_CHAIR = 4;   // seat tile (walkable, character stands here)

// Layout geometry in tiles
const BORDER  = 2;   // wall-border width
const CELL_W  = 3;   // cols per layout column  (2 desk + 1 gap)
const CELL_H  = 4;   // rows per layout row     (1 desk + 1 seat + 1 char + 1 gap)
const DESK_W  = 2;   // desk width in tiles
const SEAT_DY = 1;   // seat row below desk top

// Grid total dimensions
const G_COLS = BORDER * 2 + NCOLS_L * CELL_W;
const G_ROWS = BORDER * 2 + NROWS_L * CELL_H;

// ── Colour palettes (squad-pod palettes) ─────────────────────────────────────
const PALETTES = [
  ['#4169E1','#FDBCB4','#2C3E50'],
  ['#DC143C','#FDBCB4','#2C3E50'],
  ['#32CD32','#C68642','#2C3E50'],
  ['#9370DB','#8D5524','#2C3E50'],
  ['#FF8C00','#FDBCB4','#2C3E50'],
  ['#20B2AA','#C68642','#2C3E50'],
];

// ── Sprite generation (ported from squad-pod defaultCharacters.ts) ────────────
// 16×24 pixel colour arrays (SpriteData equivalent)

function empty16x24() {{
  return Array.from({{length:24}}, () => Array(16).fill(''));
}}
function _px(g, x, y, c) {{
  if (y>=0 && y<g.length && x>=0 && x<g[0].length) g[y][x] = c;
}}
function _row(g, x1, x2, y, c) {{
  for (let x=x1; x<=x2; x++) _px(g,x,y,c);
}}

function makeWalkDown(shirt, skin, pants) {{
  const g = empty16x24();
  // Hair
  _row(g,5,10,0,'#1a1008'); _row(g,4,11,1,'#1a1008'); _row(g,4,11,2,'#1a1008');
  // Head/face
  for (let y=2; y<8; y++) _row(g,5,10,y,skin);
  _px(g,4,5,skin); _px(g,11,5,skin);
  // Eyes + mouth
  _px(g,6,4,'#000000'); _px(g,9,4,'#000000');
  _row(g,6,9,6,'#000000');
  // Body
  for (let y=8; y<16; y++) _row(g,4,11,y,shirt);
  // Side arms
  _px(g,3,9,shirt); _px(g,12,9,shirt);
  _px(g,3,10,skin);  _px(g,12,10,skin);
  // Legs
  for (let y=16; y<24; y++) {{
    _row(g,5,6,y,pants);
    _row(g,9,10,y,pants);
  }}
  return g;
}}

// Walk frame 2 — left stride
function makeWalkFrame2(shirt, skin, pants) {{
  const g = makeWalkDown(shirt, skin, pants);
  for (let y=16; y<24; y++) {{
    _row(g,5,6,y,''); _row(g,9,10,y,'');
    _row(g,3,4,y,pants);   // left leg forward
    _row(g,9,10,y,pants);  // right leg back (same cols OK for 16px)
  }}
  _px(g,2,11,skin); _px(g,13,9,skin);
  _px(g,3,10,'');   _px(g,12,10,'');
  return g;
}}

// Walk frame 4 — right stride
function makeWalkFrame4(shirt, skin, pants) {{
  const g = makeWalkDown(shirt, skin, pants);
  for (let y=16; y<24; y++) {{
    _row(g,5,6,y,''); _row(g,9,10,y,'');
    _row(g,5,6,y,pants);   // left leg back
    _row(g,10,11,y,pants); // right leg forward
  }}
  _px(g,2,9,skin); _px(g,13,11,skin);
  return g;
}}

// Typing frame 1
function makeTypingFrame1(shirt, skin, pants) {{
  const g = empty16x24();
  _row(g,5,10,0,'#1a1008'); _row(g,4,11,1,'#1a1008'); _row(g,4,11,2,'#1a1008');
  for (let y=2; y<8; y++) _row(g,5,10,y,skin);
  _px(g,4,5,skin); _px(g,11,5,skin);
  _px(g,6,4,'#000000'); _px(g,9,4,'#000000');
  _row(g,6,9,6,'#000000');
  for (let y=8; y<16; y++) _row(g,4,11,y,shirt);
  // Arms reaching forward to keyboard
  _px(g,2,10,skin); _px(g,1,10,skin);
  _px(g,13,10,skin); _px(g,14,10,skin);
  // Shortened legs (sitting)
  for (let y=16; y<20; y++) {{
    _row(g,5,6,y,pants); _row(g,9,10,y,pants);
  }}
  return g;
}}

// Typing frame 2 — hands slightly lower
function makeTypingFrame2(shirt, skin, pants) {{
  const g = empty16x24();
  _row(g,5,10,0,'#1a1008'); _row(g,4,11,1,'#1a1008'); _row(g,4,11,2,'#1a1008');
  for (let y=2; y<8; y++) _row(g,5,10,y,skin);
  _px(g,4,5,skin); _px(g,11,5,skin);
  _px(g,6,4,'#000000'); _px(g,9,4,'#000000');
  _row(g,6,9,6,'#000000');
  for (let y=8; y<16; y++) _row(g,4,11,y,shirt);
  _px(g,2,12,skin); _px(g,1,11,skin);
  _px(g,13,12,skin); _px(g,14,11,skin);
  for (let y=16; y<20; y++) {{
    _row(g,5,6,y,pants); _row(g,9,10,y,pants);
  }}
  return g;
}}

// Build 4-frame walk + 2-frame type sprites for a palette variant index
const _spriteCache = new Map();
function buildSprites(variantIdx) {{
  if (_spriteCache.has(variantIdx)) return _spriteCache.get(variantIdx);
  const [shirt, skin, pants] = PALETTES[variantIdx % PALETTES.length];
  const s = {{
    walk:   [makeWalkDown(shirt,skin,pants), makeWalkFrame2(shirt,skin,pants),
             makeWalkDown(shirt,skin,pants), makeWalkFrame4(shirt,skin,pants)],
    typing: [makeTypingFrame1(shirt,skin,pants), makeTypingFrame2(shirt,skin,pants)],
  }};
  _spriteCache.set(variantIdx, s);
  return s;
}}

// ── Pixel-art speech bubbles (ported from squad-pod) ─────────────────────────
// 12 wide × 10 tall arrays of CSS colour strings

// Waiting / attention bubble ("?")
const BUBBLE_QUESTION = [
  ['','','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','',''],
  ['','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff',''],
  ['#fff','#fff','','','','','','','','','#fff','#fff'],
  ['#fff','#fff','','','#000','#000','#000','','','','#fff','#fff'],
  ['#fff','#fff','','','#000','','','#000','','','#fff','#fff'],
  ['#fff','#fff','','','','','','#000','','','#fff','#fff'],
  ['#fff','#fff','','','','','#000','','','','#fff','#fff'],
  ['#fff','#fff','','','','','#000','','','','#fff','#fff'],
  ['','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff',''],
  ['','','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','',''],
];

// Working / typing bubble ("...")
const BUBBLE_DOTS = [
  ['','','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','',''],
  ['','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff',''],
  ['#fff','#fff','','','','','','','','','#fff','#fff'],
  ['#fff','#fff','','#000','','#000','','#000','','','#fff','#fff'],
  ['#fff','#fff','','#000','','#000','','#000','','','#fff','#fff'],
  ['#fff','#fff','','','','','','','','','#fff','#fff'],
  ['#fff','#fff','','','','','','','','','#fff','#fff'],
  ['#fff','#fff','','','','','','','','','#fff','#fff'],
  ['','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff',''],
  ['','','#fff','#fff','#fff','#fff','#fff','#fff','#fff','#fff','',''],
];

// ── Pixel-art sprite renderer ─────────────────────────────────────────────────
// (squad-pod drawSpriteDirect)
function drawPixelSprite(ctx, sprite, x, y, zoom) {{
  const h = sprite.length, w = sprite[0] ? sprite[0].length : 0;
  for (let sy=0; sy<h; sy++) {{
    for (let sx=0; sx<w; sx++) {{
      const c = sprite[sy][sx];
      if (c && c !== '') {{
        ctx.fillStyle = c;
        ctx.fillRect(x + sx*zoom, y + sy*zoom, zoom, zoom);
      }}
    }}
  }}
}}

// ── BFS pathfinding (squad-pod findPath equivalent) ──────────────────────────
let tileMap = [];

function bfsPath(fromC, fromR, toC, toR) {{
  if (fromC===toC && fromR===toR) return [];
  const rows=tileMap.length, cols=tileMap[0].length;
  const key = (c,r) => c+','+r;
  const walkable = (c,r) => {{
    if (c<0||r<0||c>=cols||r>=rows) return false;
    const t = tileMap[r][c];
    if (c===toC && r===toR) return t!==T_WALL && t!==T_DESK && t!==T_VOID;
    return t===T_FLOOR || t===T_CHAIR;
  }};
  const queue = [{{c:fromC, r:fromR, path:[]}}];
  const visited = new Set([key(fromC,fromR)]);
  while (queue.length) {{
    const {{c,r,path}} = queue.shift();
    for (const [dc,dr] of [[0,1],[1,0],[0,-1],[-1,0]]) {{
      const nc=c+dc, nr=r+dr, nk=key(nc,nr);
      if (!visited.has(nk) && walkable(nc,nr)) {{
        visited.add(nk);
        const np = [...path, {{c:nc, r:nr}}];
        if (nc===toC && nr===toR) return np;
        queue.push({{c:nc, r:nr, path:np}});
      }}
    }}
  }}
  return null;
}}

// ── Character class (squad-pod Character equivalent) ─────────────────────────
class Character {{
  constructor(def, seatCol, seatRow, spawnCol, spawnRow) {{
    this.key      = def.key;
    this.icon     = def.ic;
    this.name     = def.nm;
    this.seatCol  = seatCol;
    this.seatRow  = seatRow;
    this.col      = spawnCol;
    this.row      = spawnRow;
    this.path     = [];
    this.moveProgress = 0;
    this.WALK_SPEED   = 0.07;
    this.state    = 'walk';   // walk | idle | type | done | error
    this.direction = 'down';  // down | left | right
    this.frameIdx  = Math.floor(Math.random()*4);
    this.frameTick = 0;
    this.status   = 'idle';
    this.bubbleType  = 'none'; // none | question | dots
    this.bubbleAlpha = 0;
    this.sprites  = buildSprites(def.variant);
    this.sparkAngle = 0;
    this._walkTo(seatCol, seatRow);
  }}

  _walkTo(tc, tr) {{
    const path = bfsPath(this.col, this.row, tc, tr);
    if (path && path.length > 0) {{
      this.path = path;
      this.state = 'walk';
      this.moveProgress = 0;
    }} else {{
      this.col = tc; this.row = tr;
      this.state = 'idle';
    }}
  }}

  update(externalStatus) {{
    this.status = externalStatus;
    this.frameTick++;

    // Walk tick (squad-pod moveProgress interpolation)
    if (this.state === 'walk' && this.path.length > 0) {{
      this.moveProgress += this.WALK_SPEED;
      if (this.moveProgress >= 1) {{
        const next = this.path.shift();
        if      (next.c > this.col) this.direction = 'right';
        else if (next.c < this.col) this.direction = 'left';
        else                         this.direction = 'down';
        this.col = next.c; this.row = next.r;
        this.moveProgress = 0;
        if (this.path.length === 0) {{
          this.direction = 'down';
          this.state = externalStatus === 'running' ? 'type'
                     : externalStatus === 'done'    ? 'done'
                     : 'idle';
          if (this.state === 'type') this._showBubble('dots');
        }}
      }}
      if (this.frameTick % 6 === 0) this.frameIdx = (this.frameIdx+1) % 4;
    }}

    // Idle → type (activated while already seated)
    if (this.state === 'idle' && externalStatus === 'running') {{
      if (this.col===this.seatCol && this.row===this.seatRow) {{
        this.state = 'type';
        this._showBubble('dots');
      }} else {{
        this._walkTo(this.seatCol, this.seatRow);
      }}
    }}

    // Typing tick
    if (this.state === 'type') {{
      if (externalStatus !== 'running') {{
        this.state = externalStatus === 'done' ? 'done' : 'idle';
      }}
      if (this.frameTick % 10 === 0) this.frameIdx = (this.frameIdx+1) % 2;
      if (this.frameTick % 160 === 0) this._showBubble('dots');
    }}

    // Terminal states
    if (externalStatus === 'done'  && this.state !== 'walk') this.state = 'done';
    if (externalStatus === 'error' && this.state !== 'walk') this.state = 'error';
    if (this.state === 'done' || this.state === 'error') {{
      if (this.frameTick % 8 === 0) this.frameIdx = (this.frameIdx+1) % 4;
    }}
    if (this.state === 'done') this.sparkAngle += 0.04;

    // Ambient idle bubble
    if (this.state === 'idle' && this.frameTick % 120 === 0) {{
      this._showBubble('question');
    }}

    // Bubble fade
    if (this.bubbleAlpha > 0) {{
      this.bubbleAlpha = Math.max(0, this.bubbleAlpha - 0.013);
      if (this.bubbleAlpha <= 0) this.bubbleType = 'none';
    }}
  }}

  _showBubble(type) {{
    this.bubbleType  = type;
    this.bubbleAlpha = 1.0;
  }}

  // Interpolated pixel position in tile-space (squad-pod moveProgress lerp)
  get pxX() {{
    if (this.state === 'walk' && this.path.length > 0) {{
      const next = this.path[0];
      return this.col * TILE + (next.c - this.col) * TILE * this.moveProgress;
    }}
    return this.col * TILE;
  }}
  get pxY() {{
    if (this.state === 'walk' && this.path.length > 0) {{
      const next = this.path[0];
      return this.row * TILE + (next.r - this.row) * TILE * this.moveProgress;
    }}
    return this.row * TILE;
  }}
  // Z-sort key (squad-pod: bottomY + CHARACTER_Z_SORT_OFFSET)
  get bottomY() {{ return this.pxY + TILE; }}

  draw(ctx, offX, offY) {{
    const sprW = 16, sprH = 24;
    // Center sprite horizontally in the tile, bottom-align vertically
    const sx = offX + this.pxX * ZOOM + Math.round((TILE*ZOOM - sprW*ZOOM) / 2);
    const sy = offY + this.pxY * ZOOM + (TILE*ZOOM - sprH*ZOOM);

    // Select sprite frame
    const sprite = this.state === 'type'
      ? this.sprites.typing[this.frameIdx % 2]
      : this.sprites.walk[this.frameIdx % 4];

    // Shadow
    ctx.save();
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(sx + sprW*ZOOM/2, sy + sprH*ZOOM + 1,
                sprW*ZOOM*0.38, 3, 0, 0, Math.PI*2);
    ctx.fill();
    ctx.restore();

    // Pixel sprite (squad-pod drawSpriteDirect)
    drawPixelSprite(ctx, sprite, sx, sy, ZOOM);

    // Done sparkles (squad-pod style Z-sorted above character)
    if (this.state === 'done') {{
      for (let i=0; i<5; i++) {{
        const a = this.sparkAngle + i/5 * Math.PI * 2;
        const r = 13 * ZOOM;
        const spx = sx + sprW*ZOOM/2 + Math.cos(a)*r;
        const spy = sy + sprH*ZOOM/2 + Math.sin(a)*r;
        ctx.save();
        ctx.globalAlpha = Math.max(0, 0.5 + Math.sin(this.sparkAngle*2+i)*0.4);
        ctx.fillStyle = i%2 ? '#FFD93D' : '#6BCF7F';
        ctx.fillRect(Math.round(spx), Math.round(spy), ZOOM, ZOOM);
        ctx.restore();
      }}
    }}

    // Error overlay
    if (this.state === 'error') {{
      ctx.save();
      ctx.globalAlpha = 0.28 + Math.sin(this.frameTick*0.15)*0.22;
      ctx.fillStyle = '#FF6B6B';
      ctx.fillRect(sx, sy, sprW*ZOOM, sprH*ZOOM);
      ctx.restore();
    }}

    // Speech bubble (squad-pod renderBubbles)
    if (this.bubbleType !== 'none' && this.bubbleAlpha > 0.05) {{
      ctx.save();
      ctx.globalAlpha = this.bubbleAlpha;
      const bSprite = this.bubbleType === 'dots' ? BUBBLE_DOTS : BUBBLE_QUESTION;
      const bw = bSprite[0].length * ZOOM;
      const bx = sx + sprW*ZOOM/2 - bw/2;
      const by = sy - bSprite.length * ZOOM - 4;
      drawPixelSprite(ctx, bSprite, bx, by, ZOOM);
      ctx.restore();
    }}

    // Name label — status colors + typeface from Munder Difflin's DESIGN.md
    // pixel-game palette (idle/thinking-working/success/blocked).
    ctx.font = `600 ${{Math.round(7*ZOOM/3)}}px "Pixelify Sans",-apple-system,sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillStyle = this.state==='type'  ? '#FFD93D'
                  : this.state==='done'  ? '#6BCF7F'
                  : this.state==='error' ? '#FF6B6B'
                  :                        '#A899B5';
    ctx.fillText(this.icon+' '+this.name, sx + sprW*ZOOM/2,
                 sy + sprH*ZOOM + 9);
    ctx.textAlign = 'left';
  }}
}}

// ── Desk furniture drawing ────────────────────────────────────────────────────
function drawDesk(ctx, col, row, offX, offY, active, deskTiles) {{
  const x  = offX + col * TS;
  const y  = offY + row * TS;
  const dw = deskTiles * TS;
  const dh = TS;

  // Wood desktop surface
  const planks = ['#5a4020','#4a3010','#5a4020','#3d2808','#4a3010'];
  for (let i=0; i<5; i++) {{
    ctx.fillStyle = planks[i % planks.length];
    const py = y + Math.round(i * dh/5);
    ctx.fillRect(x, py, dw, Math.round(dh/5)+1);
  }}
  // Edge shadows
  ctx.fillStyle = '#3d2808';
  ctx.fillRect(x, y, 3, dh);
  ctx.fillRect(x+dw-3, y, 3, dh);
  // Top highlight
  ctx.fillStyle = '#7a5828';
  ctx.fillRect(x, y, dw, 2);

  // Monitor bezel
  const mw = Math.round(dw * 0.6);
  const mh = Math.round(TS * 0.85);
  const mx = x + Math.round((dw-mw)/2);
  const my = y - mh + 2;
  ctx.fillStyle = '#141020';
  ctx.beginPath(); ctx.roundRect(mx, my, mw, mh, 3); ctx.fill();

  // Screen
  ctx.fillStyle = active ? '#001a2e' : '#08081a';
  ctx.beginPath(); ctx.roundRect(mx+3, my+3, mw-6, mh-6, 2); ctx.fill();

  if (active) {{
    // Screen glow — Munder Difflin's "status-thinking" sky token
    ctx.fillStyle = '#4ECDC4';
    ctx.globalAlpha = 0.85;
    ctx.beginPath(); ctx.roundRect(mx+3, my+3, mw-6, mh-6, 2); ctx.fill();
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = '#fff';
    const lh = Math.max(2, Math.round((mh-8)/4));
    for (let i=0; i<4; i++) {{
      const lw = (mw-8) * (0.4 + (i*11%5)*0.1);
      ctx.fillRect(mx+5, my+5+i*lh, lw, Math.max(1,lh-2));
    }}
    ctx.globalAlpha = 0.07;
    ctx.fillStyle = '#4ECDC4';
    ctx.beginPath(); ctx.roundRect(mx-4, my-4, mw+8, mh+8, 6); ctx.fill();
    ctx.globalAlpha = 1;
  }}

  // Monitor stand
  ctx.fillStyle = '#2a2040';
  ctx.fillRect(x+Math.round(dw/2)-3, y-3, 6, 5);

  // Keyboard
  ctx.fillStyle = '#1e293b';
  ctx.beginPath();
  ctx.roundRect(x+Math.round(dw*0.15), y+Math.round(dh*0.3),
                Math.round(dw*0.7),    Math.round(dh*0.35), 2);
  ctx.fill();
  ctx.fillStyle = '#334155';
  const kh = Math.round(dh*0.35);
  for (let r=0; r<2; r++) {{
    for (let k=0; k<6; k++) {{
      ctx.fillRect(x + Math.round(dw*0.17) + k*Math.round(dw*0.1),
                   y + Math.round(dh*0.33) + r*Math.round(kh/2),
                   Math.round(dw*0.08), Math.round(kh/2)-1);
    }}
  }}
}}

// ── Tile grid rendering (squad-pod renderTileGrid) ───────────────────────────
function renderFloor(ctx, offX, offY) {{
  for (let r=0; r<G_ROWS; r++) {{
    for (let c=0; c<G_COLS; c++) {{
      const tile = tileMap[r][c];
      if (tile === T_VOID) continue;
      const x = offX + c * TS, y = offY + r * TS;
      if (tile === T_WALL) {{
        ctx.fillStyle = '#100d20';
        ctx.fillRect(x, y, TS, TS);
        ctx.fillStyle = '#1a1628';
        ctx.fillRect(x, y, TS, 4);
        ctx.fillStyle = '#0a0818';
        ctx.fillRect(x, y+4, 3, TS-4);
      }} else {{
        // Alternating floor tiles (squad-pod FLOOR_A / FLOOR_B)
        ctx.fillStyle = (c+r)%2===0 ? '#1e1a2e' : '#241f38';
        ctx.fillRect(x, y, TS, TS);
        ctx.strokeStyle = '#14102a';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x+0.5, y+0.5, TS-1, TS-1);
      }}
    }}
  }}
}}

// ── Office state ──────────────────────────────────────────────────────────────
let characters = [];
let desks      = [];
let canvasW, canvasH;

function layoutToTile(sc, rowL) {{
  return {{
    tileCol: BORDER + sc * CELL_W,
    tileRow: BORDER + rowL * CELL_H,
  }};
}}

function initOffice() {{
  // Build tile map (walls on border, floor inside)
  tileMap = Array.from({{length: G_ROWS}}, (_, r) =>
    Array.from({{length: G_COLS}}, (__, c) => {{
      if (r < BORDER || r >= G_ROWS-BORDER ||
          c < BORDER || c >= G_COLS-BORDER) return T_WALL;
      return T_FLOOR;
    }})
  );

  characters = [];
  desks      = [];

  const spawnRow = G_ROWS - BORDER - 1;  // bottom walkable row

  LAYOUT.forEach((entry, idx) => {{
    const [sc, ec, rowL, ai] = entry;
    const def = AGENTS[ai];
    const {{ tileCol, tileRow }} = layoutToTile(sc, rowL);
    const span    = ec - sc + 1;
    const deskTiles = span * DESK_W;  // e.g. span=2 → 4 tiles wide

    // Mark desk tiles as blocked
    for (let dc=0; dc<deskTiles && tileCol+dc<G_COLS; dc++) {{
      if (tileRow < G_ROWS) tileMap[tileRow][tileCol+dc] = T_DESK;
    }}

    // Seat tile (centred, one row below desk)
    const seatCol = tileCol + Math.floor(deskTiles/2);
    const seatRow = tileRow + SEAT_DY;
    if (seatRow < G_ROWS && seatCol < G_COLS)
      tileMap[seatRow][seatCol] = T_CHAIR;

    desks.push({{ col:tileCol, row:tileRow, deskTiles, agentKey:def.key }});

    // Spawn each character at a distinct bottom column
    const spawnCol = Math.max(BORDER, Math.min(G_COLS-BORDER-1, BORDER+idx));
    characters.push(new Character(def, seatCol, seatRow, spawnCol, spawnRow));
  }});

  canvasW = G_COLS * TS;
  canvasH = G_ROWS * TS + 28;  // extra room for name labels
  const cv = document.getElementById('cv');
  cv.width  = canvasW; cv.height = canvasH;
  // Responsivo: encolhe com o container (mantendo proporção via height:auto),
  // mas nunca estica além do tamanho nativo do pixel-art.
  cv.style.width = '100%';
  cv.style.maxWidth = canvasW+'px';
  cv.style.height = 'auto';
  cv.style.margin = '0 auto';
}}

// ── Main render frame (squad-pod renderFrame) ─────────────────────────────────
let rafId = null;

function renderFrame() {{
  const cv = document.getElementById('cv');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvasW, canvasH);

  // 1. Floor + wall tiles
  renderFloor(ctx, 0, 0);

  // 2. Collect Z-sortable drawables: desks (furniture) + characters
  //    Squad-pod: Drawable[] sorted by z (bottomY)
  const drawables = [];

  desks.forEach(d => {{
    const status = (STATES[d.agentKey]||{{}}).status||'idle';
    const active = status==='running' || status==='done';
    drawables.push({{
      z:    (d.row + 1) * TILE,   // desk bottom in tile-space
      draw: () => drawDesk(ctx, d.col, d.row, 0, 0, active, d.deskTiles),
    }});
  }});

  characters.forEach(ch => {{
    const status = (STATES[ch.key]||{{}}).status||'idle';
    ch.update(status);
    drawables.push({{
      z:    ch.bottomY,
      draw: () => ch.draw(ctx, 0, 0),
    }});
  }});

  // Z-sort (squad-pod: drawables.sort((a,b) => a.z - b.z))
  drawables.sort((a,b) => a.z - b.z);
  drawables.forEach(d => d.draw());

  rafId = requestAnimationFrame(renderFrame);
}}

// ── Boot ──────────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {{
  initOffice();
  rafId = requestAnimationFrame(renderFrame);

  function reportHeight() {{
    const h = document.getElementById('wrap').scrollHeight + 8;
    window.parent.postMessage({{type:'streamlit:setFrameHeight', height:h}}, '*');
  }}
  setTimeout(reportHeight, 250);

  window.addEventListener('resize', () => {{
    if (rafId) cancelAnimationFrame(rafId);
    initOffice();
    rafId = requestAnimationFrame(renderFrame);
    setTimeout(reportHeight, 100);
  }});
}});
</script>
</body></html>"""
