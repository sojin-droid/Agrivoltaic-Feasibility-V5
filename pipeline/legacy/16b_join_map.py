# -*- coding: utf-8 -*-
"""16b_join_map.py — T2: inspect_dangjin_block.html 갱신
접합 15/25/35/50m 전환 버튼(≥3MW 등재, 3단 분할 적용) + 간격 히스토그램 + T3 분할 패널.
결정 자료 전용 — 채택 문구 없음."""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
J = json.load(open(os.path.join(OUT, "block_proto", "join_study.json"), encoding="utf-8"))

# 히스토그램 SVG (0~60m, 2m 빈 + 마지막 60m+)
h = J["hist"]; gs = J["gap_stats"]
counts = h["counts"]; edges = h["edges"]
mx = max(counts[1:]) or 1  # 0~2m(접촉 포함) 빈은 스케일 제외
bars = []
W, H = 560, 120
bw = W / len(counts)
for i, c in enumerate(counts):
    bh = min(H, c / mx * H)
    x = i * bw
    col = "#2c7a7b" if edges[i] < 8 else ("#b7791f" if edges[i] < 16 else "#9b2c2c" if edges[i] < 40 else "#718096")
    bars.append(f'<rect x="{x:.0f}" y="{H-bh:.0f}" width="{bw-1:.0f}" height="{bh:.0f}" fill="{col}"><title>{edges[i]}–{edges[i]+2 if i<len(counts)-1 else "120"}m: {c:,}</title></rect>')
svg = (f'<svg viewBox="0 0 {W} {H+34}" style="width:100%">' + "".join(bars) +
       f'<text x="0" y="{H+14}" font-size="10">0m</text><text x="{bw*4:.0f}" y="{H+14}" font-size="10" fill="#2c7a7b">~8m 농로대</text>'
       f'<text x="{bw*8:.0f}" y="{H+26}" font-size="10" fill="#b7791f">8–16m 구거·소로대</text>'
       f'<text x="{bw*13:.0f}" y="{H+14}" font-size="10" fill="#9b2c2c">16–40m 도로대</text>'
       f'<text x="{W-70}" y="{H+14}" font-size="10" fill="#718096">40m+ 단절</text></svg>')

html = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>프로토타입 — 당진 블록 후보지구 (접합 거리 결정 자료)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:'Malgun Gothic',sans-serif}
 #map{position:absolute;inset:0}
 #panel{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;padding:12px 14px;
   border-radius:8px;box-shadow:0 1px 8px rgba(0,0,0,.3);width:330px;font-size:12.5px;
   line-height:1.55;max-height:94vh;overflow-y:auto}
 #panel h1{font-size:14px;margin:0 0 6px}
 .warn{background:#e6fffa;border:1px solid #319795;padding:4px 6px;border-radius:4px;margin-bottom:8px}
 button{margin:2px 2px 2px 0;padding:3px 8px;font-size:12px;cursor:pointer;border:1px solid #888;background:#f5f5f5;border-radius:4px}
 button.on{background:#2c7a7b;color:#fff;border-color:#2c7a7b}
 td,th{padding:1px 6px 1px 0;text-align:right} th:first-child,td:first-child{text-align:left}
 hr{border:none;border-top:1px solid #ddd;margin:8px 0}
</style></head><body>
<div id="map"></div>
<div id="panel">
 <h1>당진 블록 후보 — 접합 거리 결정 자료</h1>
 <div class="warn"><b>사용자 결정 대기</b>: 접합 거리(15/25/35/50m) · 분할 규칙 승인.
 아래 버튼으로 4안 직접 비교 (≥3MW 등재, 3단 분할 ①리 ②소유 ③콤팩트 적용).</div>
 <b>접합 거리</b>
 <span id="jbtns"></span>
 <table id="jstat"></table>
 <hr>
 <b>t 필터 — 블록 개인소유 비율 ≤ t (미확인 &gt;20% 분리)</b><br>
 <span id="tbtns"></span>
 <table id="stat"></table>
 <hr>
 <b>적격 필지 최근접 간격 히스토그램</b>
 <div style="color:#888">직접 접촉(&lt;0.5m) __TOUCH__% 제외 후 분포 · 비접촉 중앙값 __MED__m · P75 __P75__ · P90 __P90__</div>
 __SVG__
 <hr>
 <b>T3 — 최대 블록 3단 분할 (①법정리 ②소유 경계 ③콤팩트)</b>
 <table id="t3"></table>
 <div style="color:#888">②소유 단계가 3MW 미만 파편을 다수 생성 — 승인 검토 포인트</div>
 <hr>
 <b>우선 검토 순위 — 개인소유 낮은 순</b>
 <div id="rank" style="max-height:170px;overflow-y:auto;margin-top:4px"></div>
 <details><summary id="unkSum" style="cursor:pointer;color:#b7791f"></summary>
 <div id="unkList" style="max-height:120px;overflow-y:auto"></div></details>
</div>
<script>
const D = __DATA__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OSM',maxZoom:19}).addTo(map);
function col(mw){return mw<5?'#b2f5ea':mw<10?'#4fd1c5':mw<30?'#2c7a7b':'#234e52';}
const grp = L.featureGroup().addTo(map);
let JOIN='25', T=0.30, polys=[];
function build(){
  grp.clearLayers(); polys=[];
  D.by_join[JOIN].records.forEach(r=>{
    const p = L.polygon(r.poly.map(ring=>ring.map(q=>[q[1],q[0]])),
      {color:col(r.mw),weight:1.2,fillColor:col(r.mw),fillOpacity:.5});
    p.bindPopup(`<b>${r.bid}</b> (${r.how})<br><b>${r.mw} MW</b> · 필지 ${r.n.toLocaleString()}<br>`+
      `개인소유 ${r.indiv!=null?(r.indiv*100).toFixed(1):'?'}% · 미확인 ${(r.unk*100).toFixed(1)}%`);
    p._r=r; p.addTo(grp); polys.push(p);});
  const v = D.by_join[JOIN];
  document.getElementById('jstat').innerHTML =
    `<tr><th>안</th><th>세그</th><th>합계MW</th><th>최대 블록</th></tr>`+
    Object.entries(D.by_join).map(([k,x])=>
      `<tr${k===JOIN?' style="background:#e6fffa;font-weight:bold"':''}><td>${k}m</td><td>${x.seg_n}</td><td>${x.seg_mw.toLocaleString()}</td><td>${x.max_block_mw.toLocaleString()}MW</td></tr>`).join('');
  refresh();
}
function refresh(){
  let n=0, mw=0; const vis=[];
  polys.forEach(p=>{
    const r=p._r, ok = r.unk<=0.20 && r.indiv!=null && r.indiv<=T;
    if(ok){n++; mw+=r.mw; vis.push(p);}
    p.setStyle(ok?{opacity:1,fillOpacity:.5}:{opacity:.12,fillOpacity:.05});
  });
  document.getElementById('stat').innerHTML =
    `<tr><td>등재(개인≤${T} · 미확인≤20%)</td><td><b>${n}</b>개 · <b>${mw.toFixed(0)} MW</b></td></tr>`;
  vis.sort((a,b)=>a._r.indiv-b._r.indiv);
  document.getElementById('rank').innerHTML = vis.slice(0,30).map((p,i)=>{const r=p._r;
    return `<div class="rk" data-b="${r.bid}" style="cursor:pointer;display:flex;justify-content:space-between;border-bottom:1px dotted #eee;padding:1px 2px">`+
      `<span>${i+1}. ${r.bid}</span><span>개인 <b>${(r.indiv*100).toFixed(1)}%</b> · 미확인 ${(r.unk*100).toFixed(1)}% · ${r.mw}MW</span></div>`;}).join('')
    + (vis.length>30?`<div style="color:#888">… 외 ${vis.length-30}</div>`:'');
  const fl = polys.filter(p=>p._r.unk>0.20);
  document.getElementById('unkSum').innerText = `소유 확인 필요 블록 (${fl.length}) — 미확인 >20%`;
  document.getElementById('unkList').innerHTML = fl.map(p=>{const r=p._r;
    return `<div class="rk" data-b="${r.bid}" style="cursor:pointer;display:flex;justify-content:space-between;padding:1px 2px">`+
      `<span>${r.bid}</span><span>미확인 <b>${(r.unk*100).toFixed(1)}%</b> · ${r.mw}MW</span></div>`;}).join('');
  document.querySelectorAll('.rk').forEach(el=>el.onclick=()=>{
    const p=polys.find(q=>q._r.bid==el.dataset.b);
    if(p){map.fitBounds(p.getBounds().pad(0.4)); p.openPopup();}});
}
document.getElementById('jbtns').innerHTML = Object.keys(D.by_join).map(k=>
  `<button class="jb${k==='25'?' on':''}" data-v="${k}">${k}m</button>`).join('');
document.getElementById('tbtns').innerHTML = [0.10,0.20,0.30,0.40,0.50,1.1].map(t=>
  `<button class="tf${t===0.30?' on':''}" data-v="${t}">${t>1?'전체':t.toFixed(2)}</button>`).join('');
document.getElementById('t3').innerHTML =
  '<tr><th>안</th><th>최대MW</th><th>①리</th><th>②소유잔여</th><th>③콤팩트</th><th>세그</th><th>&lt;3MW 탈락</th></tr>'+
  Object.entries(D.t3).map(([k,v])=>`<tr><td>${k}m</td><td>${v['최대블록MW'].toLocaleString()}</td><td>${v['리분할대상']}</td><td>${v['소유분할잔여']}</td><td>${v['콤팩트절단']}</td><td>${v['세그먼트수']}</td><td>${v['3MW미만탈락']}</td></tr>`).join('');
document.addEventListener('click', e=>{
  if(e.target.classList.contains('jb')){document.querySelectorAll('.jb').forEach(x=>x.classList.remove('on'));
    e.target.classList.add('on'); JOIN=e.target.dataset.v; build();}
  if(e.target.classList.contains('tf')){document.querySelectorAll('.tf').forEach(x=>x.classList.remove('on'));
    e.target.classList.add('on'); T=parseFloat(e.target.dataset.v); refresh();}});
build();
map.fitBounds(grp.getBounds());
</script></body></html>"""

html = (html.replace("__TOUCH__", str(gs["touch_pct"])).replace("__MED__", str(gs["median_pos"]))
        .replace("__P75__", str(gs["p75"])).replace("__P90__", str(gs["p90"]))
        .replace("__SVG__", svg)
        .replace("__DATA__", json.dumps(J, ensure_ascii=False, separators=(",", ":"))))
out = os.path.join(OUT, "inspect_dangjin_block.html")
open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out} ({os.path.getsize(out)/1e6:.1f} MB)")
