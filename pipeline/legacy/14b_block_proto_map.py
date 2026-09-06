# -*- coding: utf-8 -*-
"""14b_block_proto_map.py — 블록 피벗 프로토타입 지도 (inspect_dangjin_block.html)
기존 inspect_dangjin.html(구 방식)과 나란히 검수 — 기존 산출물 보존."""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
D = json.load(open(os.path.join(OUT, "block_proto", "44270_blocks.json"), encoding="utf-8"))

html = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>프로토타입 — 당진 블록 후보지구 (방법론 피벗 검수용)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:'Malgun Gothic',sans-serif}
 #map{position:absolute;inset:0}
 #panel{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;
   padding:12px 14px;border-radius:8px;box-shadow:0 1px 8px rgba(0,0,0,.3);
   width:310px;font-size:12.5px;line-height:1.55;max-height:92vh;overflow-y:auto}
 #panel h1{font-size:14px;margin:0 0 6px}
 .warn{background:#e6fffa;border:1px solid #319795;padding:4px 6px;border-radius:4px;margin-bottom:8px}
 button{margin:2px 2px 2px 0;padding:3px 8px;font-size:12px;cursor:pointer;
   border:1px solid #888;background:#f5f5f5;border-radius:4px}
 button.on{background:#2c7a7b;color:#fff;border-color:#2c7a7b}
 td{padding:1px 6px 1px 0} hr{border:none;border-top:1px solid #ddd;margin:8px 0}
</style></head><body>
<div id="map"></div>
<div id="panel">
 <h1>프로토타입 — 당진 블록 후보지구</h1>
 <div class="warn"><b>방법론 피벗 검수용</b> — 후보 = 연접 블록(≤25m 잠정), ≥3MW 등재,
 50MW 초과 시 ①법정리 ②주축 누적용량 분할. 성장·병합 없음(하천·철도 자동 단절).
 구 방식 지도(inspect_dangjin.html)와 나란히 비교.</div>
 <div>등재 세그먼트 <b>__N_SEG__개 · __TOT_MW__MW</b> (소유 무관 총량)</div>
 <hr>
 <b>t 필터 — 블록 개인소유 비율 ≤ t (미확인 &gt;20% 상시 분리)</b><br>
 <button class="tf" data-v="0.10">0.10</button>
 <button class="tf" data-v="0.20">0.20</button>
 <button class="tf on" data-v="0.30">0.30</button>
 <button class="tf" data-v="0.40">0.40</button>
 <button class="tf" data-v="0.50">0.50</button>
 <button class="tf" data-v="1.1">전체</button>
 <table id="stat"></table>
 <hr>
 <b>우선 검토 순위 — 개인소유 비율 낮은 순</b>
 <div style="color:#888">t 필터 적용분 · 클릭 이동</div>
 <div id="rank" style="max-height:200px;overflow-y:auto;margin-top:4px"></div>
 <details style="margin-top:6px"><summary id="unkSum" style="cursor:pointer;color:#b7791f"></summary>
 <div id="unkList" style="max-height:140px;overflow-y:auto"></div></details>
 <hr>
 <b>신구 t 스윕 비교 (미확인≤20%)</b>
 <table id="comp" style="font-size:11.5px"></table>
 <div style="color:#888">신+하위구획 보완안은 완료 보고 표 참조</div>
</div>
<script>
const D = __DATA__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OSM',maxZoom:19}).addTo(map);
function col(mw){return mw<5?'#b2f5ea':mw<10?'#4fd1c5':mw<30?'#2c7a7b':'#234e52';}
const grp = L.featureGroup().addTo(map);
const polys = D.records.map(r=>{
  const p = L.polygon(r.poly.map(ring=>ring.map(q=>[q[1],q[0]])),
    {color:col(r.mw),weight:1.2,fillColor:col(r.mw),fillOpacity:.5});
  p.bindPopup(`<b>블록 ${r.bid}</b> (${r.how})<br><b>${r.mw} MW</b> · 필지 ${r.n.toLocaleString()}<br>`+
    `개인소유 ${r.indiv!=null?(r.indiv*100).toFixed(1):'?'}% · 미확인 ${(r.unk*100).toFixed(1)}%`);
  p._r = r; p.addTo(grp); return p;});
map.fitBounds(grp.getBounds());
let T = 0.30;
function refresh(){
  let n=0, mw=0;
  const vis=[];
  polys.forEach(p=>{
    const r=p._r, ok = r.unk<=0.20 && (r.indiv==null ? false : r.indiv<=T);
    if(ok){n++; mw+=r.mw; vis.push(p);}
    p.setStyle(ok?{opacity:1,fillOpacity:.5}:{opacity:.12,fillOpacity:.05});
  });
  document.getElementById('stat').innerHTML =
    `<tr><td>등재(개인≤${T>1?'전체':T} · 미확인≤20%)</td><td><b>${n}</b>개 · <b>${mw.toFixed(0)} MW</b></td></tr>`;
  vis.sort((a,b)=>a._r.indiv-b._r.indiv);
  document.getElementById('rank').innerHTML = vis.slice(0,40).map((p,i)=>{
    const r=p._r;
    return `<div class="rk" data-b="${r.bid}" style="cursor:pointer;display:flex;justify-content:space-between;border-bottom:1px dotted #eee;padding:1px 2px">`+
      `<span>${i+1}. ${r.bid} (${r.how==='무분할'?'단일':r.how})</span>`+
      `<span>개인 <b>${(r.indiv*100).toFixed(1)}%</b> · 미확인 ${(r.unk*100).toFixed(1)}% · ${r.mw}MW</span></div>`;
  }).join('') + (vis.length>40?`<div style="color:#888">… 외 ${vis.length-40}</div>`:'');
  const fl = polys.filter(p=>p._r.unk>0.20);
  document.getElementById('unkSum').innerText = `소유 확인 필요 블록 (${fl.length}개) — 미확인 >20%`;
  document.getElementById('unkList').innerHTML = fl.sort((a,b)=>b._r.unk-a._r.unk).map(p=>{
    const r=p._r;
    return `<div class="rk" data-b="${r.bid}" style="cursor:pointer;display:flex;justify-content:space-between;border-bottom:1px dotted #eee;padding:1px 2px">`+
      `<span>${r.bid}</span><span>개인 ${(r.indiv*100).toFixed(1)}% · 미확인 <b>${(r.unk*100).toFixed(1)}%</b> · ${r.mw}MW</span></div>`;}).join('');
  document.querySelectorAll('.rk').forEach(el=>el.onclick=()=>{
    const p=polys.find(q=>q._r.bid==el.dataset.b);
    if(p){map.fitBounds(p.getBounds().pad(0.4)); p.openPopup();}});
}
refresh();
document.querySelectorAll('.tf').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tf').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); T=parseFloat(b.dataset.v); refresh();});
document.getElementById('comp').innerHTML =
  '<tr><th>t</th><th>구 exec</th><th>신 블록</th></tr>'+
  D.comp.map(c=>`<tr><td>${c.t.toFixed(2)}</td><td>${c['구'].toLocaleString()}</td><td>${c['신'].toLocaleString()} (${Math.round(c['비율']*100)}%)</td></tr>`).join('');
</script></body></html>"""

tot = sum(r["mw"] for r in D["records"])
html = (html.replace("__N_SEG__", str(len(D["records"])))
        .replace("__TOT_MW__", f"{tot:,.0f}")
        .replace("__DATA__", json.dumps(D, ensure_ascii=False, separators=(",", ":"))))
out = os.path.join(OUT, "inspect_dangjin_block.html")
open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out} ({os.path.getsize(out)/1e6:.1f} MB) / 세그먼트 {len(D['records'])} · {tot:,.0f}MW")
