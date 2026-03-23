#!/usr/bin/env python3
"""
HalluMaze Visual Storyteller — v2
각 모델의 미로 탈출 시도를 인터랙티브 HTML로 시각화

Usage:
    source ~/.claude/env/shared.env && python3 visualize_maze.py
    python3 visualize_maze.py --seed 4004 --size 5
"""
from __future__ import annotations

import sys, os, re, json, argparse
from datetime import datetime

def _load_env(path: str):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if m:
                    k, v = m.group(1), m.group(2).strip('"\'')
                    if k not in os.environ:
                        os.environ[k] = v
    except FileNotFoundError:
        pass

_load_env("~/.claude/env/shared.env")
_load_env(".envrc")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'files'))

from hallumaze import (
    LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner,
    PromptBuilder, BenchmarkResult
)


# ── Provider patch ──

def _strip_think(text: str) -> str:
    import re as _re
    stripped = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL).strip()
    return stripped if stripped else text

def _call_minimax(self, prompt, max_tokens, system=""):
    import openai
    client = openai.OpenAI(
        api_key=self.api_key,
        base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    )
    # MiniMax-M2.5 추론 모델: <think> 블록이 ~3000+ 토큰 소모 → 최소 8000 필요
    effective_tokens = max(max_tokens, 8000)
    resp = client.chat.completions.create(
        model=self.model, max_tokens=effective_tokens,
        messages=[
            {"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    return _strip_think(resp.choices[0].message.content)

def _call_glm(self, prompt, max_tokens, system=""):
    import anthropic
    client = anthropic.Anthropic(
        api_key=self.api_key,
        base_url=os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    )
    msg = client.messages.create(
        model=self.model, max_tokens=max_tokens,
        system=system or PromptBuilder.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

_orig_call = LLMProvider.call

def _patched_call(self, prompt, max_tokens, system=""):
    if self.provider == "minimax": return _call_minimax(self, prompt, max_tokens, system)
    if self.provider == "glm":     return _call_glm(self, prompt, max_tokens, system)
    return _orig_call(self, prompt, max_tokens, system)

LLMProvider.call = _patched_call


# ── Helpers ──

def build_providers():
    out = []
    k = os.environ.get("MINIMAX_API_KEY")
    if k:
        m = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")
        out.append(LLMProvider(provider="minimax", api_key=k, model=m))
        print(f"  [+] MiniMax / {m}")
    k = os.environ.get("GLM_API_KEY")
    if k:
        m = os.environ.get("GLM_MODEL", "glm-4.7")
        out.append(LLMProvider(provider="glm", api_key=k, model=m))
        print(f"  [+] GLM / {m}")
    return out


def serialize_maze(maze: MazeEngine) -> dict:
    """Serialize cell walls to JSON for the canvas renderer."""
    N = maze.N
    # walls[r][c] = {N, S, E, W} — True means wall exists (BLOCKED)
    walls = []
    for r in range(N):
        row = []
        for c in range(N):
            cell = maze.cells[r][c]
            row.append({
                "N": bool(cell.N),
                "S": bool(cell.S),
                "E": bool(cell.E),
                "W": bool(cell.W),
            })
        walls.append(row)

    # mirage_traps: list of (r, c, dir, nr, nc) tuples
    mirage_positions = [[t[0], t[1]] for t in (maze.mirage_traps or [])]

    return {
        "N": N,
        "walls": walls,
        "start": [0, 0],
        "end": [N - 1, N - 1],
        "solution": [list(p) for p in (maze.solution or [])],
        "mirage_positions": mirage_positions,
    }


def serialize_result(result: BenchmarkResult) -> dict:
    """Extract path steps from BenchmarkResult for animation."""
    # extracted_path: list of [r, c]
    path = result.extracted_path or []

    # steps: list of StepRecord with hallucination/backtrack flags
    step_list = []
    for i, s in enumerate(result.steps or []):
        # steps are dicts (from asdict(StepRecord))
        if isinstance(s, dict):
            step_list.append({
                "step": s.get("step", i),
                "r": s.get("r", 0),
                "c": s.get("c", 0),
                "direction": s.get("direction", "?"),
                "is_hallucination": bool(s.get("is_hallucination", False)),
                "is_backtrack": bool(s.get("is_backtrack", False)),
                "is_loop": bool(s.get("is_loop", False)),
                "confidence": s.get("confidence"),
            })
        else:
            step_list.append({
                "step": s.step,
                "r": s.r,
                "c": s.c,
                "direction": s.direction,
                "is_hallucination": s.is_hallucination,
                "is_backtrack": s.is_backtrack,
                "is_loop": s.is_loop,
                "confidence": s.confidence,
            })

    return {
        "model": result.model,
        "provider": result.provider,
        "solved": bool(result.sr and result.sr >= 1.0),
        "mei": round(result.mei or 0.0, 3),
        "score": round(result.hallumaze_score or 0.0, 3),
        "hallucination_count": result.hallucination_count or 0,
        "backtrack_count": result.backtrack_count or 0,
        "loop_count": result.loop_count or 0,
        "brs": round(result.brs or 0.0, 3),
        "latency_s": result.latency_s or 0,
        "path": path,
        "steps": step_list,
    }


# ── HTML template ──

HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>HalluMaze — Model Escape Comparison</title>
<style>
:root{--bg:#0f1117;--card:#161926;--border:#252840;--text:#e2e8f0;--muted:#566;
  --green:#10b981;--red:#ef4444;--orange:#f97316;--yellow:#eab308;
  --blue:#3b82f6;--purple:#8b5cf6;--teal:#14b8a6;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;padding:20px 16px;}
h1{text-align:center;font-size:1.5rem;margin-bottom:4px;}
.sub{text-align:center;color:var(--muted);font-size:.85rem;margin-bottom:20px;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1100px;margin:0 auto 20px;}
@media(max-width:680px){.grid{grid-template-columns:1fr;}}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;}
.card-hd{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
.card-hd h2{font-size:1rem;font-weight:700;}
.badge{font-size:.7rem;padding:2px 8px;border-radius:99px;background:var(--border);font-weight:600;}
canvas{display:block;margin:0 auto;max-width:100%;}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:12px;}
.m-box{background:#0d0f1a;border-radius:8px;padding:8px 4px;text-align:center;}
.m-val{font-size:1.1rem;font-weight:700;}
.m-lbl{font-size:.65rem;color:var(--muted);margin-top:2px;}
.controls{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;
  margin:12px auto 8px;max-width:1100px;}
button{background:var(--border);color:var(--text);border:1px solid #353858;
  border-radius:8px;padding:6px 16px;cursor:pointer;font-size:.82rem;}
button:hover{background:#252840;}
button.active{background:var(--blue);border-color:var(--blue);}
.speed-row{display:flex;align-items:center;gap:6px;font-size:.8rem;}
.speed-row input{width:90px;}
.legend{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;
  font-size:.75rem;margin:8px 0 16px;}
.ld{display:flex;align-items:center;gap:4px;}
.ld span{width:11px;height:11px;border-radius:3px;display:inline-block;}
.log-box{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:14px;max-width:1100px;margin:0 auto 16px;}
.log-box h3{font-size:.9rem;margin-bottom:8px;}
.log-scroll{max-height:160px;overflow-y:auto;font-size:.75rem;font-family:monospace;}
.lr{padding:2px 0;border-bottom:1px solid #1a1d2e;}
.lr.hall{color:var(--red);}
.lr.back{color:var(--orange);}
.lr.loop{color:var(--yellow);}
.lr.ok{color:var(--muted);}
.lr.solve{color:var(--green);font-weight:700;}
.cmp-box{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:16px;max-width:1100px;margin:0 auto;}
.cmp-box h3{font-size:.9rem;margin-bottom:10px;}
table{width:100%;border-collapse:collapse;font-size:.82rem;}
th{color:var(--muted);font-weight:600;padding:7px 10px;border-bottom:1px solid var(--border);text-align:left;}
td{padding:8px 10px;border-bottom:1px solid #1a1d2e;}
.win{color:var(--green);font-weight:700;}
.lose{color:var(--muted);}
</style>
</head>
<body>
<h1>HalluMaze — Metacognition Escape Visualization</h1>
<div class="sub" id="sub"></div>
<div class="controls">
  <button id="btnPlay">&#9654; Play</button>
  <button id="btnPause">&#10074;&#10074; Pause</button>
  <button id="btnReset">&#10226; Reset</button>
  <label><input type="checkbox" id="chkSolution" checked> Show solution</label>
  <div class="speed-row">Speed: <input type="range" id="spd" min="1" max="20" value="6">
    <span id="spdLbl">6x</span></div>
</div>
<div class="legend">
  <div class="ld"><span style="background:#10b981"></span>Path</div>
  <div class="ld"><span style="background:#ef4444"></span>Hallucination</div>
  <div class="ld"><span style="background:#f97316"></span>Backtrack</div>
  <div class="ld"><span style="background:#eab308"></span>Loop</div>
  <div class="ld"><span style="background:#1e3a5f"></span>Solution</div>
  <div class="ld"><span style="background:#2d1f4e"></span>Mirage zone</div>
  <div class="ld"><span style="background:#34d399"></span>Start</div>
  <div class="ld"><span style="background:#f43f5e"></span>End</div>
</div>
<div class="grid" id="grid"></div>
<div class="log-box"><h3>Step Log</h3><div class="log-scroll" id="log"></div></div>
<div class="cmp-box"><h3>Model Comparison</h3><table id="cmp"></table></div>

<script>
(function(){
var D = __DATA__;
var M = D.maze, N = M.N;
var CELL = Math.min(Math.floor(460/N), 64), PAD = 20;
var W = N*CELL+PAD*2, H = N*CELL+PAD*2;

function mkCanvas(r, idx){
  var card=document.createElement('div'); card.className='card';
  var hd=document.createElement('div'); hd.className='card-hd';
  var h2=document.createElement('h2'); h2.textContent=r.model+' ('+r.provider+')';
  var badge=document.createElement('span'); badge.className='badge';
  badge.id='badge'+idx; badge.textContent='Step 0/'+r.steps.length;
  hd.appendChild(h2); hd.appendChild(badge); card.appendChild(hd);
  var cv=document.createElement('canvas');
  cv.id='cv'+idx; cv.width=W; cv.height=H; cv.style.width='100%';
  card.appendChild(cv);
  var mx=document.createElement('div'); mx.className='metrics';
  [['MEI','mei'],['Solved','solved'],['Hall.','hallucination_count'],['BT','backtrack_count']].forEach(function(x){
    var b=document.createElement('div'); b.className='m-box';
    var v=document.createElement('div'); v.className='m-val'; v.id='mv_'+x[0]+'_'+idx;
    var l=document.createElement('div'); l.className='m-lbl'; l.textContent=x[0];
    b.appendChild(v); b.appendChild(l); mx.appendChild(b);
  });
  card.appendChild(mx); return card;
}

var grid=document.getElementById('grid');
D.results.forEach(function(r,i){ grid.appendChild(mkCanvas(r,i)); });

// ── Maze draw ──
function drawBase(ctx, showSol){
  ctx.fillStyle='#09090f'; ctx.fillRect(0,0,W,H);
  // cells bg
  for(var r=0;r<N;r++) for(var c=0;c<N;c++){
    var x=PAD+c*CELL, y=PAD+r*CELL;
    ctx.fillStyle='#141627'; ctx.fillRect(x+1,y+1,CELL-2,CELL-2);
  }
  // solution overlay
  if(showSol && M.solution){
    ctx.fillStyle='#0d2a4a';
    M.solution.forEach(function(p){ ctx.fillRect(PAD+p[1]*CELL+2,PAD+p[0]*CELL+2,CELL-4,CELL-4); });
  }
  // mirage
  if(M.mirage_positions){
    ctx.fillStyle='#1e1040';
    M.mirage_positions.forEach(function(p){ ctx.fillRect(PAD+p[1]*CELL+4,PAD+p[0]*CELL+4,CELL-8,CELL-8); });
  }
  // walls
  ctx.strokeStyle='#4a5080'; ctx.lineWidth=2;
  for(var r=0;r<N;r++) for(var c=0;c<N;c++){
    var w=M.walls[r][c];
    var x=PAD+c*CELL, y=PAD+r*CELL;
    ctx.beginPath();
    if(w.N){ctx.moveTo(x,y);ctx.lineTo(x+CELL,y);}
    if(w.S){ctx.moveTo(x,y+CELL);ctx.lineTo(x+CELL,y+CELL);}
    if(w.W){ctx.moveTo(x,y);ctx.lineTo(x,y+CELL);}
    if(w.E){ctx.moveTo(x+CELL,y);ctx.lineTo(x+CELL,y+CELL);}
    ctx.stroke();
  }
  // border
  ctx.strokeStyle='#6070a0'; ctx.lineWidth=2.5;
  ctx.strokeRect(PAD,PAD,N*CELL,N*CELL);
  // start / end
  function dot(r,c,col,lbl){
    var cx=PAD+c*CELL+CELL/2, cy=PAD+r*CELL+CELL/2;
    ctx.fillStyle=col; ctx.beginPath(); ctx.arc(cx,cy,CELL*0.32,0,Math.PI*2); ctx.fill();
    ctx.fillStyle='#fff'; ctx.font='bold '+Math.max(9,CELL*0.28)+'px sans-serif';
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(lbl,cx,cy);
  }
  dot(0,0,'#34d399','S'); dot(N-1,N-1,'#f43f5e','E');
}

function colorOf(s){
  if(s.is_hallucination) return '#ef4444';
  if(s.is_loop)          return '#eab308';
  if(s.is_backtrack)     return '#f97316';
  return '#10b981';
}

function drawPath(ctx, steps, upTo){
  for(var i=0;i<=upTo&&i<steps.length;i++){
    var s=steps[i];
    var alpha=0.35+0.65*(i/Math.max(upTo,1));
    ctx.globalAlpha=alpha;
    ctx.fillStyle=colorOf(s);
    ctx.fillRect(PAD+s.c*CELL+3,PAD+s.r*CELL+3,CELL-6,CELL-6);
  }
  ctx.globalAlpha=1;
  if(upTo>=0&&upTo<steps.length){
    var s=steps[upTo];
    ctx.fillStyle='#93c5fd';
    ctx.beginPath();
    ctx.arc(PAD+s.c*CELL+CELL/2,PAD+s.r*CELL+CELL/2,CELL*0.3,0,Math.PI*2);
    ctx.fill();
  }
}

function setMetric(key,idx,val,isGood){
  var el=document.getElementById('mv_'+key+'_'+idx);
  if(!el)return; el.textContent=val;
  if(isGood!==undefined) el.style.color=isGood?'#10b981':'#ef4444';
}

function updateMetrics(idx, result, upTo){
  var steps=result.steps.slice(0,upTo+1);
  var halls=steps.filter(function(s){return s.is_hallucination;}).length;
  var backs=steps.filter(function(s){return s.is_backtrack||s.is_loop;}).length;
  var solved=steps.some(function(s){return s.r===N-1&&s.c===N-1;});
  setMetric('MEI',idx,result.mei.toFixed(3));
  setMetric('Solved',idx,solved?'YES':'NO',solved);
  setMetric('Hall.',idx,halls,halls===0);
  setMetric('BT',idx,backs);
  var badge=document.getElementById('badge'+idx);
  badge.textContent='Step '+(Math.min(upTo+1,result.steps.length))+'/'+result.steps.length;
  if(solved){badge.style.background='#064e3b';badge.style.color='#34d399';}
}

// ── Animation ──
var frame=0, playing=false, timer=null, showSol=true;
var maxFrames=Math.max.apply(null,D.results.map(function(r){return r.steps.length;}));
function speed(){return parseInt(document.getElementById('spd').value);}
function delay(){return Math.max(40,1200-speed()*55);}

function render(){
  var showSolNow=document.getElementById('chkSolution').checked;
  D.results.forEach(function(r,idx){
    var cv=document.getElementById('cv'+idx);
    var ctx=cv.getContext('2d');
    drawBase(ctx,showSolNow);
    var f=Math.min(frame,r.steps.length-1);
    if(f>=0) drawPath(ctx,r.steps,f);
    updateMetrics(idx,r,f);
  });
  // log: longest model
  var li=0,mx=0; D.results.forEach(function(r,i){if(r.steps.length>mx){mx=r.steps.length;li=i;}});
  updateLog(li,Math.min(frame,D.results[li].steps.length-1));
}

function updateLog(idx,upTo){
  var log=document.getElementById('log'); log.textContent='';
  var steps=D.results[idx].steps;
  var start=Math.max(0,upTo-40);
  for(var i=start;i<=upTo&&i<steps.length;i++){
    var s=steps[i];
    var row=document.createElement('div'); row.className='lr';
    var cls='ok';
    if(s.is_hallucination) cls='hall';
    else if(s.is_loop) cls='loop';
    else if(s.is_backtrack) cls='back';
    else if(s.r===N-1&&s.c===N-1) cls='solve';
    row.className='lr '+cls;
    var tag=D.results[idx].model.split('-')[0];
    var pos='('+s.r+','+s.c+')';
    var evt=s.is_hallucination?'HALL':s.is_loop?'LOOP':s.is_backtrack?'BACK':'MOVE';
    if(s.r===N-1&&s.c===N-1) evt='SOLVED!';
    var conf=s.confidence!==null?' ['+s.confidence+'%]':'';
    row.textContent='['+tag+' #'+i+'] '+pos+' '+evt+' '+s.direction+conf;
    log.appendChild(row);
  }
  log.scrollTop=log.scrollHeight;
}

function tick(){
  if(frame<maxFrames-1){frame++;render();timer=setTimeout(tick,delay());}
  else{playing=false;document.getElementById('btnPlay').classList.remove('active');}
}

document.getElementById('btnPlay').addEventListener('click',function(){
  if(!playing){playing=true;this.classList.add('active');tick();}
});
document.getElementById('btnPause').addEventListener('click',function(){
  playing=false;clearTimeout(timer);document.getElementById('btnPlay').classList.remove('active');
});
document.getElementById('btnReset').addEventListener('click',function(){
  playing=false;clearTimeout(timer);
  document.getElementById('btnPlay').classList.remove('active');
  frame=0;render();
});
document.getElementById('spd').addEventListener('input',function(){
  document.getElementById('spdLbl').textContent=this.value+'x';
});
document.getElementById('chkSolution').addEventListener('change',function(){render();});

// ── Comparison table ──
function buildTable(){
  var tbl=document.getElementById('cmp');
  var thead=document.createElement('thead');
  var hr=document.createElement('tr');
  ['Metric','Winner'].concat(D.results.map(function(r){return r.model;})).forEach(function(h){
    var th=document.createElement('th'); th.textContent=h; hr.appendChild(th);
  });
  thead.appendChild(hr); tbl.appendChild(thead);
  var tbody=document.createElement('tbody');
  var rows=[
    {l:'MEI',k:'mei',hi:true},
    {l:'HalluScore',k:'score',hi:true},
    {l:'Solved',k:'solved',hi:true,fmt:function(v){return v?'YES':'NO';}},
    {l:'Hallucinations',k:'hallucination_count',hi:false},
    {l:'Backtracks',k:'backtrack_count',hi:false},
    {l:'BRS (Bias Resist)',k:'brs',hi:true},
    {l:'Latency (s)',k:'latency_s',hi:false},
  ];
  rows.forEach(function(row){
    var vals=D.results.map(function(r){return r[row.k];});
    var best=row.hi?Math.max.apply(null,vals):Math.min.apply(null,vals);
    var wi=vals.indexOf(best);
    var tr=document.createElement('tr');
    var tl=document.createElement('td'); tl.textContent=row.l; tr.appendChild(tl);
    var tw=document.createElement('td'); tw.textContent=D.results[wi].model;
    tw.className='win'; tr.appendChild(tw);
    vals.forEach(function(v,i){
      var td=document.createElement('td');
      td.textContent=row.fmt?row.fmt(v):(typeof v==='number'?v.toFixed(3):v);
      td.className=i===wi?'win':'lose'; tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
}

// ── Init ──
document.getElementById('sub').textContent=
  'Seed '+D.seed+' | '+N+'x'+N+' maze | '+D.timestamp;
buildTable();
render();
})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=4004)
    ap.add_argument("--size", type=int, default=5, choices=[5, 7, 9])
    ap.add_argument("--group", type=str, default="A", choices=["A", "B", "C"])
    ap.add_argument("--no-mirage", action="store_true")
    ap.add_argument("--output", type=str, default=None)
    args = ap.parse_args()

    print("\n" + "="*60)
    print("  HalluMaze Visual Storyteller v2")
    print("="*60 + "\n")

    print("  [Providers]")
    providers = build_providers()
    if not providers:
        print("  ERROR: No providers found.")
        sys.exit(1)

    config = MazeConfig(
        size=args.size,
        use_mirage=not args.no_mirage,
        use_confidence=True,
        ariadne_mode=args.group,
        max_tokens=3000,
    )

    maze = MazeEngine(size=args.size, seed=args.seed)
    print(f"\n  [Maze] seed={maze.seed} size={maze.N}x{maze.N} "
          f"sol_len={len(maze.solution or [])} dead_ends={maze.dead_ends}")
    print(maze.ascii_render())

    runner = BenchmarkRunner(config)
    for p in providers:
        print(f"\n  Running {p.model}...")
        result = runner.run_single(p, maze)
        status = "SOLVED" if result.sr and result.sr >= 1.0 else "FAILED"
        print(f"  -> {status} | MEI={result.mei:.3f} | hall={result.hallucination_count} "
              f"| bt={result.backtrack_count} | steps={len(result.steps)} | {result.latency_s:.1f}s")
        if result.error:
            print(f"  ERROR: {result.error}")

    maze_data = serialize_maze(maze)
    results_data = [serialize_result(r) for r in runner.results]

    payload = {
        "seed": args.seed,
        "size": args.size,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "maze": maze_data,
        "results": results_data,
    }

    data_json = json.dumps(payload, ensure_ascii=False)
    html = HTML.replace("__DATA__", data_json)

    out = args.output or f"hallumaze_visual_seed{args.seed}_{args.size}x{args.size}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    json_out = out.replace(".html", "_data.json")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n  [Done]")
    print(f"  HTML: {os.path.abspath(out)}")
    print(f"  JSON: {os.path.abspath(json_out)}")
    print(f"  Open: file://{os.path.abspath(out)}")


if __name__ == "__main__":
    main()
