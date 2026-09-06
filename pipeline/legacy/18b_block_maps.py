# -*- coding: utf-8 -*-
"""18b_block_maps.py — E2 본 산출 지도·index (블록 방법론, 2026-07-16 잠금)
inspect_{sgg}.html 재생성(블록판) + inspect_index.html. 구 클러스터 지도는
pipeline_out/legacy_cluster_maps/ 로 이동 보존.
순위 사양(2026-07-16): 단위=등재 세그, 라벨 "블록 {bid} · {위치} · {MW} · {n}필지 · {ha}",
같은 모블록은 그룹 접기, 정렬=개인소유 낮은 순, 미확인>20% 분리."""
import os, sys, io, json, glob, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
BL = os.path.join(OUT, "blocks")
NAMES = {"44270": "당진", "44180": "보령", "44200": "아산", "44130": "천안시", "44210": "서산", "44800": "홍성", "41590": "화성",
         "41220": "평택", "41463": "용인기흥", "41271": "안산상록", "41390": "시흥",
         "41500": "이천", "41480": "파주", "41570": "김포", "44810": "예산",
         "41461": "용인처인", "41465": "용인수지", "41273": "안산단원",
         "28200": "인천남동", "46230": "광양", "46130": "여수", "47111": "포항남",
         "47113": "포항북", "47190": "구미", "31110": "울산중", "31140": "울산남",
         "31170": "울산동", "31200": "울산북", "31710": "울주"}
ULSAN = {"31110", "31140", "31170", "31200", "31710"}  # 표시: 그룹 헤더 (판정은 구·군별)

LEG = os.path.join(OUT, "legacy_cluster_maps")
os.makedirs(LEG, exist_ok=True)
SUMMARY_ALL = json.load(open(os.path.join(OUT, "sgg_summary.json"), encoding="utf-8"))

TPL = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>본 산출 — __NAME__ 블록 후보지구 (S3·접합25m)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:'Malgun Gothic',sans-serif}
 #map{position:absolute;inset:0}
 #panel{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;padding:12px 14px;
  border-radius:8px;box-shadow:0 1px 8px rgba(0,0,0,.3);width:330px;font-size:12.5px;
  line-height:1.55;max-height:94vh;overflow-y:auto}
 #panel h1{font-size:14px;margin:0 0 6px}
 .lock{background:#ebf8ff;border:1px solid #3182ce;padding:4px 6px;border-radius:4px;margin-bottom:8px}
 button{margin:2px 2px 2px 0;padding:3px 8px;font-size:12px;cursor:pointer;border:1px solid #888;background:#f5f5f5;border-radius:4px}
 button.on{background:#2b6cb0;color:#fff;border-color:#2b6cb0}
 td,th{padding:1px 6px 1px 0;text-align:right} th:first-child,td:first-child{text-align:left}
 hr{border:none;border-top:1px solid #ddd;margin:8px 0}
 details.grp{border-bottom:1px dotted #eee} details.grp summary{cursor:pointer;padding:1px 2px}
 .seg{display:flex;justify-content:space-between;padding:1px 2px 1px 14px;cursor:pointer}
</style></head><body>
<div id="map"></div>
<div id="panel">
 <h1>본 산출 — __NAME__ 블록 후보지구</h1>
 <div class="lock"><b>방법론 잠금(2026-07-16)</b> — 블록(접합 25m)·3단 분할·파편 재병합.
 공식 등재 = 세그 ≥3MW · 판정 = 개인소유≤t ∧ 미확인≤20% 합산</div>
 <b>시나리오</b> <button id="s3b" class="on">S3 (__S3N__세그·__S3MW__MW)</button>
 <button id="s0b">S0 (__S0N__세그·__S0MW__MW)</button>
 <hr>
 <b>t 필터 — 세그 개인소유 비율 ≤ t</b><br><span id="tbtns"></span>
 <table id="stat"></table>
 <div id="judge" style="color:#555"></div>
 <hr>
 <b>우선 검토 순위 — 개인소유 비율 낮은 순</b>
 <div style="color:#888">등재 세그(≥3MW) · 같은 모블록은 접기 · 클릭 이동 · 미확인&gt;20% 하단 분리</div>
 <div id="rank" style="max-height:300px;overflow-y:auto;margin-top:4px"></div>
 <details><summary id="unkSum" style="cursor:pointer;color:#b7791f"></summary>
 <div id="unkList" style="max-height:140px;overflow-y:auto"></div></details>
 <hr>
 <div style="background:#f7fafc;border:1px solid #cbd5e0;border-radius:6px;padding:8px 10px">
  <b>시군 요약</b> <span style="color:#888">(sgg_summary + blocks_sweep)</span>
  <div>__CARD__</div>
 </div>
</div>
<script>
const DS = {S3: __DATA_S3__, S0: __DATA_S0__};
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OSM',maxZoom:19}).addTo(map);
function col(mw){return mw<5?'#c6dbef':mw<10?'#6baed6':mw<30?'#2171b5':'#08306b';}
const grp = L.featureGroup().addTo(map);
let SCN='S3', T=0.30, polys=[];
const lbl = r => `블록 ${r.bid} · ${r.loc} · ${r.mw}MW · ${r.n.toLocaleString()}필지 · ${r.ha}ha`;
function build(){
  grp.clearLayers(); polys=[];
  DS[SCN].records.forEach(r=>{
    const p = L.polygon(r.poly.map(g=>g.map(q=>[q[1],q[0]])),
      r.sub ? {color:'#276749',weight:1.6,dashArray:'4 3',fillColor:'#48bb78',fillOpacity:.55}
            : {color:col(r.mw),weight:1.2,fillColor:col(r.mw),fillOpacity:.5});
    p.bindPopup(`<b>${lbl(r)}</b><br>${r.sub?'<b>하위구획</b> (모세그 '+r.parent+' 탈락 시 등재)':'분할: '+r.how}<br>개인소유 ${r.indiv!=null?(r.indiv*100).toFixed(1):'?'}% · 미확인 ${(r.unk*100).toFixed(1)}%`);
    p._r=r; p.addTo(grp); polys.push(p);});
  refresh();
  if (polys.length) map.fitBounds(grp.getBounds());
}
function refresh(){
  // 모세그 통과 → 모 표시·하위 숨김 / 탈락 → 모 흐림·하위구획 표시 (이중 계상 없음)
  const passP = {};
  polys.forEach(p=>{const r=p._r;
    if(!r.sub) passP[r.bid] = (r.unk<=0.20 && r.indiv!=null && r.indiv<=T);});
  let n=0, mw=0; const vis=[];
  polys.forEach(p=>{
    const r=p._r;
    const ok = r.sub ? !passP[r.parent] : passP[r.bid];
    if(ok){n++; mw+=r.mw; vis.push(r);}
    p.setStyle(ok?{opacity:1,fillOpacity:.55}:{opacity:r.sub?0:.12,fillOpacity:r.sub?0:.05});
  });
  document.getElementById('stat').innerHTML =
   `<tr><td>등재(개인 ${T>1?'전체':'≤'+T} · 미확인≤20%)</td><td><b>${n}</b>세그 · <b>${mw.toFixed(0)} MW</b></td></tr>`;
  const s = DS[SCN].summary;
  document.getElementById('judge').innerHTML =
   `판정(t=0.30 기준): <b>${s.status_t30}</b> · b=${s.b_mw_t30.toLocaleString()}MW · 문턱 t50=${s.threshold_t_50} / t100=${s.threshold_t_100}`;
  // 그룹 순위: 모블록별 최저 indiv로 정렬
  const g = {};
  vis.forEach(r=>{(g[r.block]=g[r.block]||[]).push(r);});
  const groups = Object.values(g).map(a=>a.sort((x,y)=>x.indiv-y.indiv))
    .sort((a,b)=>a[0].indiv-b[0].indiv);
  const segRow = r => `<div class="seg" data-b="${r.bid}"><span>${lbl(r)}</span>`+
    `<span>개인 <b>${(r.indiv*100).toFixed(1)}%</b>·미확인 ${(r.unk*100).toFixed(1)}%</span></div>`;
  let rank = 0;
  document.getElementById('rank').innerHTML = groups.slice(0,30).map(a=>{
    rank++;
    if(a.length===1) return `<div class="seg" style="padding-left:2px" data-b="${a[0].bid}">`+
      `<span><b>${rank}.</b> ${lbl(a[0])}</span><span>개인 <b>${(a[0].indiv*100).toFixed(1)}%</b></span></div>`;
    const tot = a.reduce((s,r)=>s+r.mw,0);
    return `<details class="grp"><summary><b>${rank}.</b> ${a[0].loc.split(' ')[0]} 모블록 #${a[0].block} — 구획 ${a.length}개 · ${tot.toFixed(0)}MW · 최저 개인 ${(a[0].indiv*100).toFixed(1)}% <span class='seg' data-b='${a[0].bid}' style='color:#2b6cb0;padding:0'>[이동]</span></summary>`+
      a.map(segRow).join('')+`</details>`;
  }).join('') + (groups.length>30?`<div style="color:#888">… 외 ${groups.length-30} 모블록</div>`:'');
  const fl = polys.map(p=>p._r).filter(r=>r.unk>0.20);
  document.getElementById('unkSum').innerText = `소유 확인 필요 세그 (${fl.length}) — 미확인 >20%`;
  document.getElementById('unkList').innerHTML = fl.sort((a,b)=>b.unk-a.unk).map(segRow).join('');
  document.querySelectorAll('.seg').forEach(el=>el.onclick=()=>{
    const p=polys.find(q=>q._r.bid==el.dataset.b);
    if(p){map.fitBounds(p.getBounds().pad(0.4)); p.openPopup();}});
}
document.getElementById('tbtns').innerHTML=[0.10,0.20,0.30,0.40,0.50,1.1].map(t=>
 `<button class="tf${t===0.30?' on':''}" data-v="${t}">${t>1?'전체':t.toFixed(2)}</button>`).join('');
document.addEventListener('click',e=>{
 if(e.target.classList.contains('tf')){document.querySelectorAll('.tf').forEach(x=>x.classList.remove('on'));
   e.target.classList.add('on'); T=parseFloat(e.target.dataset.v); refresh();}
 if(e.target.id==='s3b'||e.target.id==='s0b'){SCN=e.target.id==='s3b'?'S3':'S0';
   document.getElementById('s3b').classList.toggle('on',SCN==='S3');
   document.getElementById('s0b').classList.toggle('on',SCN==='S0'); build();}});
build();
</script></body></html>"""


def card_html(sgg):
    C = SUMMARY_ALL.get(sgg, {})
    if not C:  # B 지역: 잠재량 직접 산출, 수요·산단은 수집 예정
        pf = pd.read_parquet(os.path.join(OUT, "parcels_final", f"{sgg}.parquet"),
                             columns=["s0_eligible", "s2_eligible", "area_m2"])
        C = {"s0_mw": round(pf[pf.s0_eligible == 1].area_m2.sum() * 0.045 / 1000, 1),
             "s3_mw": round(pf[pf.s2_eligible == 1].area_m2.sum() * 0.045 / 1000, 1),
             "demand_note": "한전 수요 xlsx 미수록 — 수동 다운로드 대기", "complex_covered": False}
    dem = (f"수요 {C['demand_gwh_3yr']:,}GWh/년 · S3 발전 {C.get('s3_gen_gwh','?')}GWh({C.get('s3_demand_pct','?')}%)"
           if C.get("demand_gwh_3yr") else "수요: 수집 예정")
    return (f"① 잠재량(소유 무관): S0 {C.get('s0_mw',0):,}MW / S3 {C.get('s3_mw',0):,}MW<br>"
            f"② {dem}<br><span style='color:#888'>{C.get('demand_note','')}</span><br>"
            f"③ 주요 산단: {', '.join(C.get('main_complexes') or []) if C.get('complex_covered') else '산정 예정'}")


def gen(sgg):
    s3 = json.load(open(os.path.join(BL, f"{sgg}_S3.json"), encoding="utf-8"))
    s0 = json.load(open(os.path.join(BL, f"{sgg}_S0.json"), encoding="utf-8"))
    html = (TPL.replace("__NAME__", NAMES.get(sgg, sgg))
            .replace("__S3N__", str(s3["summary"]["seg_n"])).replace("__S3MW__", f"{s3['summary']['seg_mw']:,.0f}")
            .replace("__S0N__", str(s0["summary"]["seg_n"])).replace("__S0MW__", f"{s0['summary']['seg_mw']:,.0f}")
            .replace("__CARD__", card_html(sgg))
            .replace("__DATA_S3__", json.dumps(s3, ensure_ascii=False, separators=(",", ":")))
            .replace("__DATA_S0__", json.dumps(s0, ensure_ascii=False, separators=(",", ":"))))
    name = "inspect_dangjin.html" if sgg == "44270" else f"inspect_{sgg}.html"
    old = os.path.join(OUT, name)
    if os.path.exists(old) and not os.path.exists(os.path.join(LEG, name)):
        shutil.copy2(old, os.path.join(LEG, name))
    open(old, "w", encoding="utf-8").write(html)
    return name, os.path.getsize(old) / 1e6


def index_page():
    sweep = json.load(open(os.path.join(OUT, "blocks_sweep_summary.json"), encoding="utf-8"))
    BADGE = {"유력": ("#276749", "#c6f6d5"), "지정 가능": ("#975a16", "#fefcbf"),
             "요건 미달": ("#9b2c2c", "#fed7d7")}
    rows = sorted(sweep.items(), key=lambda kv: -kv[1].get("S3", {}).get("b_mw_t30", 0))
    # 울산은 그룹으로 묶어 뒤에 배치 (판정은 구·군별 유지 — 2026-07-16 확정)
    rows = ([kv for kv in rows if kv[0] not in ULSAN] +
            [("__ULSAN__", None)] + [kv for kv in rows if kv[0] in ULSAN])
    cells = []
    for sgg, v in rows:
        if sgg == "__ULSAN__":
            cells.append('<tr><td colspan="6" style="background:#f0f4f8;text-align:left">'
                         '<b>울산광역시</b> <span style="color:#888">(판정은 구·군별 — 표시 그룹)</span></td></tr>')
            continue
        if sgg not in NAMES:
            continue
        s3, s0 = v.get("S3", {}), v.get("S0", {})
        st = s3.get("status_t30", "?")
        fg, bg = BADGE.get(st, ("#555", "#eee"))
        page = "inspect_dangjin.html" if sgg == "44270" else f"inspect_{sgg}.html"
        fmt = lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) else "-"
        cells.append(f"""<tr><td><a href="{page}"><b>{NAMES[sgg]}</b></a> <span style="color:#888">{sgg}</span></td>
 <td><span style="color:{fg};background:{bg};padding:1px 7px;border-radius:9px;font-weight:bold">{st}</span></td>
 <td><b>{fmt(s3.get('b_mw_t30'))}</b></td><td>{s3.get('threshold_t_50','-')} / {s3.get('threshold_t_100','-')}</td>
 <td>{s3.get('seg_n','-')} / {fmt(s3.get('seg_mw'))}</td>
 <td>{fmt(s0.get('b_mw_t30'))}</td></tr>""")
    html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>본 산출 목록 — 블록 후보지구 (방법론 잠금 2026-07-16)</title>
<style>body{{font-family:'Malgun Gothic',sans-serif;max-width:920px;margin:24px auto;font-size:14px}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:5px 8px;text-align:right}}
td:first-child,th:first-child{{text-align:left}}
.lock{{background:#ebf8ff;border:1px solid #3182ce;padding:6px 10px;border-radius:4px}}</style></head><body>
<h2>본 산출 — 시군별 블록 후보지구 (A 지역 19개 코드)</h2>
<div class="lock">방법론 잠금(2026-07-16): 블록 접합 25m(간격 실측 근거) · ≥3MW 등재 ·
3단 분할(①리 ②소유 ③콤팩트, 파편 재병합) · 판정 = 개인소유≤t ∧ 미확인≤20% 합산
(<50 미달 / 50–100 지정 가능 / ≥100 유력, t=0.30 기준). 배포 승격 대상 — 검수 후 규칙 변경 없음 목표</div>
<table><tr><th>시군</th><th>판정(S3·t0.30)</th><th>실행가능 MW</th><th>문턱 t (50/100)</th>
<th>S3 세그 n/MW(소유무관)</th><th>S0 b(t0.30)</th></tr>{''.join(cells)}</table>
<p style="color:#666">구 클러스터 지도는 legacy_cluster_maps/ 보존 · 생성 18b_block_maps.py</p></body></html>"""
    open(os.path.join(OUT, "inspect_index.html"), "w", encoding="utf-8").write(html)


if __name__ == "__main__":
    sggs = (sys.argv[1].split(",") if len(sys.argv) > 1 and sys.argv[1] != "all"
            else [os.path.basename(f).split("_")[0] for f in
                  sorted(glob.glob(os.path.join(BL, "*_S3.json")))])
    for sgg in sggs:
        try:
            name, mb = gen(sgg)
            print(f"  {sgg}: {name} ({mb:.1f}MB)", flush=True)
        except Exception as e:
            print(f"[ERR] {sgg}: {e}", flush=True)
    index_page()
    print("inspect_index.html (블록판) 갱신")
