# -*- coding: utf-8 -*-
"""09_inspect_map.py — 검수용 지도 생성 (inspect_dangjin.html)
목적: P95 병합 추인 / 세장형 지구 / 후보지구 규모 하한 — 3개 예약 결정의 검토 입력.
입력: pipeline_out/clusters/44270_*_S3_t30{,_merged}.json + parcels_final/44270.parquet
출력: pipeline_out/inspect_dangjin.html (로컬 열람용, Leaflet CDN)
사용: python 09_inspect_map.py [sgg=44270]
"""
import os, sys, io, json, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
SGG = sys.argv[1] if len(sys.argv) > 1 else "44270"
NAMES = {"44270": "당진", "44180": "보령", "44200": "아산", "44131": "천안동남",
         "44133": "천안서북", "44210": "서산", "44800": "홍성", "41590": "화성",
         "41220": "평택", "41463": "용인기흥", "41271": "안산상록", "41390": "시흥",
         "41500": "이천", "41480": "파주", "41570": "김포",
         "44810": "예산", "41461": "용인처인", "41465": "용인수지", "41273": "안산단원"}
NAME = NAMES.get(SGG, SGG)

SUMMARY = json.load(open(os.path.join(OUT, "sgg_summary.json"), encoding="utf-8")).get(SGG, {})

# ── 표시 폴리곤: 편입 필지 union (2026-07-14 확정 — convex hull 폐기) ──
import geopandas as gpd
from shapely.ops import unary_union, transform as shp_transform
from pyproj import Transformer
_TR = Transformer.from_crs(5186, 4326, always_xy=True).transform

mem_mrg = json.load(open(os.path.join(OUT, "clusters", f"{SGG}_members_S3_t30_merged.json"), encoding="utf-8"))
mem_pre = json.load(open(os.path.join(OUT, "clusters", f"{SGG}_members_S3_t30.json"), encoding="utf-8"))
_need = set(p for ps in mem_mrg.values() for p in ps) | set(p for ps in mem_pre.values() for p in ps)
_g = gpd.read_file(os.path.join(BASE, "Base", "Base", f"{SGG}.gpkg"))
_pc = next(c for c in _g.columns if c.lower() == "pnu")
_g = _g.rename(columns={_pc: "pnu"})[["pnu", "geometry"]]
_g["pnu"] = _g["pnu"].astype(str).str.zfill(19)
_g = _g[_g["pnu"].isin(_need)].to_crs(epsg=5186)
_sp = os.path.join(OUT, "nojimok_repair", "supplement", f"{SGG}_geom.gpkg")
if os.path.exists(_sp):
    _s = gpd.read_file(_sp)[["pnu", "geometry"]]
    _s["pnu"] = _s["pnu"].astype(str).str.zfill(19)
    _s = _s[_s["pnu"].isin(_need)].to_crs(epsg=5186)
    _g = pd.concat([_g[~_g["pnu"].isin(set(_s["pnu"]))], _s], ignore_index=True)
GEOM = dict(zip(_g["pnu"], _g["geometry"]))


def union_rings(pnus):
    """필지 union → 4326 외곽 링 목록 (표시용: +15m 접합, -12m 수축, 5m 단순화)"""
    geoms = [GEOM[p] for p in pnus if p in GEOM]
    if not geoms:
        return []
    u = unary_union(geoms).buffer(15).buffer(-12).simplify(5)
    u = shp_transform(_TR, u)
    polys = u.geoms if u.geom_type == "MultiPolygon" else [u]
    return [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in polys]


pre = json.load(open(os.path.join(OUT, "clusters", f"{SGG}_clusters_S3_t30.json"), encoding="utf-8"))
mrg = json.load(open(os.path.join(OUT, "clusters", f"{SGG}_clusters_S3_t30_merged.json"), encoding="utf-8"))
una = json.load(open(os.path.join(OUT, "clusters", f"{SGG}_unassigned_S3_t30_merged.json"), encoding="utf-8"))
pf = pd.read_parquet(os.path.join(OUT, "parcels_final", f"{SGG}.parquet"),
                     columns=["pnu", "lon", "lat"])
pf = pf.set_index("pnu").loc[[p for p in una if p in pf.set_index("pnu").index if True]] \
    if False else pf[pf["pnu"].isin(set(una))]
un_pts = [[round(r.lon, 5), round(r.lat, 5)] for r in pf.itertuples()]


def enrich(cl, members):
    out = []
    for c in cl["clusters"]:
        eq_d = 2 * math.sqrt(c["area_m2"] / math.pi)
        out.append({"id": c["cluster_id"], "n": c["n"], "mw": c["mw"],
                    "ha": round(c["area_m2"] / 10000, 1),
                    "diam": c["diameter_m"],
                    "elong": round(c["diameter_m"] / eq_d, 1) if eq_d else 0,
                    "indiv": c["indiv_ratio"], "unk": c["unknown_owner_ratio"],
                    "emds": c["emds"],
                    "bc": c.get("block_count"), "mbm": c.get("max_block_mw"),
                    "mbs": c.get("max_block_share"),
                    "exec": c.get("exec_mw", 0) or 0, "eb": c.get("exec_blocks", 0),
                    "official": bool(c.get("official")),
                    "poly": union_rings(members[str(c["cluster_id"])])})
    return out


data = {"name": NAME, "sgg": SGG,
        "summary_pre": pre["summary"], "summary_mrg": mrg["summary"],
        "pre": enrich(pre, mem_pre), "mrg": enrich(mrg, mem_mrg), "unassigned": un_pts}

html = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검수용 — __NAME__ 후보지구 (S3·t0.30, P95 병합)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:'Malgun Gothic',sans-serif}
 #map{position:absolute;inset:0}
 #panel{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;
   padding:12px 14px;border-radius:8px;box-shadow:0 1px 8px rgba(0,0,0,.3);
   width:300px;font-size:12.5px;line-height:1.55;max-height:92vh;overflow-y:auto}
 #panel h1{font-size:14px;margin:0 0 6px}
 .warn{background:#fff3cd;border:1px solid #ffc107;padding:4px 6px;border-radius:4px;margin-bottom:8px}
 .row{display:flex;justify-content:space-between}
 button{margin:2px 2px 2px 0;padding:3px 8px;font-size:12px;cursor:pointer;
   border:1px solid #888;background:#f5f5f5;border-radius:4px}
 button.on{background:#2b6cb0;color:#fff;border-color:#2b6cb0}
 .leg{display:flex;align-items:center;gap:6px;margin:1px 0}
 .sw{width:14px;height:14px;border-radius:3px;display:inline-block}
 hr{border:none;border-top:1px solid #ddd;margin:8px 0}
 td{padding:1px 6px 1px 0}
</style></head><body>
<div id="map"></div>
<div id="panel">
 <h1>검수용 — __NAME__ 후보지구</h1>
 <div class="warn">내부 검수 전용 (P95 병합 <b>추인 대기</b> / 세장형·규모 하한 <b>미결</b>) — 배포 금지</div>
 <div>S3 적격 · 개인소유 비율 상한 t=0.30 · 갱신 원장 기준</div>
 <div>병합 규칙: r = 내부 간격 P95 = <b>__R_LOCAL__m</b> · 병합 __N_MERGED__건 (거부: 50MW __REJ_CAP__ / 지름 __REJ_DIAM__) · <b>__N_PRE__ → __N_MRG__지구</b> · __TOT_MW__MW</div>
 <hr>
 <b>레이어</b><br>
 <button id="bMrg" class="on">병합 후 (__N_MRG__)</button>
 <button id="bPre">병합 전 (__N_PRE__)</button>
 <button id="bUn">미편입 적격 필지 (__N_UN__)</button>
 <hr>
 <b>규모 하한 필터 — 실행 MW 기준 (공식 3MW, 파편 블록 집계 제외)</b><br>
 <button class="mw" data-v="1">1MW</button>
 <button class="mw on" data-v="3">3MW</button>
 <button class="mw" data-v="5">5MW</button>
 <button class="mw" data-v="7">7MW</button>
 <button class="mw" data-v="10">10MW</button>
 <div id="mwMode"></div>
 <table id="mwStat"></table>
 <div id="official" style="color:#555"></div>
 <hr>
 <b>세장형 강조 (기준 분리 — 지표 확정은 미결)</b><br>
 <button id="bDiam">지름 ≥ 3km</button>
 <button id="bElong">세장도 ≥ 6</button>
 <div id="longStat"></div>
 <hr>
 <div style="background:#f7fafc;border:1px solid #cbd5e0;border-radius:6px;padding:8px 10px;margin:2px 0">
  <b>시군 요약</b> <span style="color:#888">(data_contract: sgg_summary)</span>
  <div style="margin-top:4px"><b>① 잠재량 총량</b> <span style="color:#888">(하한 미적용·소유 무관)</span><br>
   S0 __C_S0N__필지 · <b>__C_S0MW__MW</b> / S3 __C_S3N__필지 · <b>__C_S3MW__MW</b> (S3÷S0 __C_RATIO__배)</div>
  <div style="margin-top:4px"><b>② 전력 수요 대비</b><br>__C_DEMAND__</div>
  <div style="margin-top:4px"><b>③ 공공·법인 소유 중심 후보</b> <span style="color:#888">(공식=최대 연접 블록 ≥3MW · 미확인 ≤20%)</span><br>
   <b>__C_LN__지구 · __C_LMW__MW</b> — S3 총량의 <b>__C_SHARE__%</b><br>
   <b>특구 요건(50MW) 대비 __C_PCT50__%</b> · 판정 <b>__C_STATUS__</b> · 통과 t=__C_T50__ (100MW: t=__C_T100__)<br>
   산단 거리(등재 지구): __C_DIST__<br>주요 산단: __C_CPLX__<br>
   <span style="color:#888">참고: 전체 공식 지구 __C_OFFN__개 · __C_OFFMW__MW (소유 무관)</span></div>
 </div>
 <hr>
 <b>우선 검토 순위 — 개인소유 비율 낮은 순</b>
 <div style="color:#888">현재 하한 필터 적용분 · 소유주 미확인 &gt;20% 지구는 하단 분리 · 클릭 시 이동</div>
 <div id="rank" style="max-height:220px;overflow-y:auto;margin-top:4px"></div>
 <details style="margin-top:6px"><summary id="unkSum" style="cursor:pointer;color:#b7791f"></summary>
 <div id="unkList" style="max-height:160px;overflow-y:auto"></div></details>
 <hr>
 <b>MW 구간 (병합 후 채색)</b>
 <div class="leg"><span class="sw" style="background:#c6dbef"></span>&lt; 3MW</div>
 <div class="leg"><span class="sw" style="background:#6baed6"></span>3–5MW</div>
 <div class="leg"><span class="sw" style="background:#2171b5"></span>5–10MW</div>
 <div class="leg"><span class="sw" style="background:#08306b"></span>≥ 10MW</div>
 <div class="leg"><span class="sw" style="border:2px dashed #777;background:none"></span>병합 전 윤곽</div>
 <div class="leg"><span class="sw" style="background:#d0d0d0"></span>미편입 필지</div>
 <hr>
 <div style="color:#666">세장도 = 지름 ÷ 등면적원 지름.<br>팝업: 지구 클릭.</div>
</div>
<script>
const D = __DATA__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  {attribution:'&copy; OpenStreetMap', maxZoom: 19}).addTo(map);
function col(mw){return mw<3?'#c6dbef':mw<5?'#6baed6':mw<10?'#2171b5':'#08306b';}  // 실행 MW 기준 채색
function popup(c,tag){return `<b>${tag} #${c.id}</b>${c.official?' <span style="color:#2b6cb0">[공식]</span>':''}<br>필지 ${c.n.toLocaleString()} · ${c.ha} ha · 명목 ${c.mw} MW · <b>실행 ${c.exec??0} MW</b>${c.eb?` (≥3MW 블록 ${c.eb}개)`:''}<br>`+
 (c.bc!=null?`연접 블록 ${c.bc}개 · 최대 블록 ${c.mbm} MW (${(c.mbs*100).toFixed(0)}%)<br>`:'')+
 `지름 ${(c.diam/1000).toFixed(2)} km · 세장도 ${c.elong}<br>`+
 `개인소유 비율 ${(c.indiv*100).toFixed(1)}% · 소유주 미확인 ${(c.unk*100).toFixed(1)}%<br>`+
 `읍면동: ${c.emds.join(', ')}`;}
const isDiam = c => c.diam >= 3000, isElong = c => c.elong >= 6;

const gMrg = L.featureGroup(), gPre = L.featureGroup();
const rings = c => c.poly.map(ring => ring.map(q=>[q[1],q[0]]));  // 필지 union 표시 (hull 폐기)
const mrgPolys = D.mrg.map(c => {
  const p = L.polygon(rings(c),
    {color: col(c.exec), weight:1.2, fillColor: col(c.exec), fillOpacity:.45});
  p.bindPopup(popup(c,'병합 후')); p._c = c; p.addTo(gMrg); return p;});
D.pre.forEach(c => L.polygon(rings(c),
    {color:'#777', weight:1, dashArray:'4 3', fill:false})
  .bindPopup(popup(c,'병합 전')).addTo(gPre));
// 미편입 필지(93k)는 개별 마커 대신 커스텀 캔버스 레이어로 일괄 렌더 (즉시 생성 시 렌더러 정지)
const UnLayer = L.Layer.extend({
  onAdd(m){this._m=m; this._c=L.DomUtil.create('canvas','leaflet-layer');
    this._c.style.pointerEvents='none'; m.getPanes().overlayPane.appendChild(this._c);
    m.on('moveend zoomend resize', this._d, this); this._d();},
  onRemove(m){L.DomUtil.remove(this._c); m.off('moveend zoomend resize', this._d, this);},
  _d(){const m=this._m, s=m.getSize(), tl=m.containerPointToLayerPoint([0,0]);
    L.DomUtil.setPosition(this._c, tl); this._c.width=s.x; this._c.height=s.y;
    const ctx=this._c.getContext('2d'); ctx.fillStyle='rgba(120,120,120,.5)';
    const b=m.getBounds();
    for(const p of D.unassigned){
      if(p[1]<b.getSouth()||p[1]>b.getNorth()||p[0]<b.getWest()||p[0]>b.getEast()) continue;
      const q=m.latLngToContainerPoint([p[1],p[0]]);
      ctx.fillRect(q.x-1, q.y-1, 2.5, 2.5);}}
});
const gUn = new UnLayer();
gMrg.addTo(map);
map.fitBounds(gMrg.getBounds());

let minMW = 3, hlDiam = false, hlElong = false;
const OFF = D.mrg.filter(c=>c.official);  // 공식 = 최대 연접 블록 ≥3MW (2026-07-15)
const OFF_MW = OFF.reduce((s,c)=>s+c.exec,0);  // 실행 MW 합산
function refresh(){
  let n=0, mw=0, ha=0, nd=0, ne=0;
  mrgPolys.forEach(p=>{
    const c=p._c, show = c.exec >= minMW;  // 하한 필터 = 실행 MW
    if(show){n++; mw+=c.exec; ha+=c.ha; if(isDiam(c)) nd++; if(isElong(c)) ne++;}
    let st;
    if(!show) st = {opacity:0, fillOpacity:0};
    else if(hlDiam && isDiam(c))
      st = {color:'#d62728', weight:2.5, dashArray:null, fillColor:'#d62728', fillOpacity:.5, opacity:1};
    else if(hlElong && isElong(c))
      st = {color:'#e07b00', weight:2.5, dashArray:null, fillColor:'#e07b00', fillOpacity:.5, opacity:1};
    else st = {color:col(c.exec), weight:1.2, dashArray:null, fillColor:col(c.exec), fillOpacity:.45, opacity:1};
    p.setStyle(st);
  });
  const cut = D.mrg.length - n;
  document.getElementById('mwMode').innerHTML = minMW === 3
    ? '<b style="color:#2b6cb0">공식 집계 기준 (3MW)</b>'
    : '<b style="color:#b7791f">탐색 기준 — 화면 집계만 갱신 (공식 수치 아님)</b>';
  document.getElementById('mwStat').innerHTML =
    `<tr><td>표시 지구</td><td><b>${n}</b> (필터 미달 ${cut})</td></tr>`+
    `<tr><td>합계</td><td>${mw.toFixed(1)} MW · ${ha.toFixed(0)} ha</td></tr>`;
  document.getElementById('official').innerHTML =
    `공식(실행 MW=≥3MW 블록 합산): ${OFF.length}지구 · ${OFF_MW.toFixed(1)} MW`;
  // 우선 검토 순위: 미확인 >10% 분리(귀속재산 밀집 등 역전 방지, 2026-07-14 결함 수정)
  // 정렬 키 = 확인 필지 기준 개인소유 비율(indiv_ratio) 유지
  const UNK_TH = 0.20;  // 기준선 20% (2026-07-14 사양 ③ 확정)
  const vis = mrgPolys.filter(p => p._c.exec >= minMW)
    .sort((a,b) => a._c.indiv - b._c.indiv);
  const rankable = vis.filter(p => p._c.unk <= UNK_TH);
  const flagged  = vis.filter(p => p._c.unk >  UNK_TH);
  const row = (p, i) => {
    const c = p._c;
    return `<div class="rk" data-id="${c.id}" style="cursor:pointer;padding:1px 2px;`+
      `display:flex;justify-content:space-between;border-bottom:1px dotted #eee">`+
      `<span>${i!==null ? (i+1)+'. ' : ''}지구 #${c.id}</span>`+
      `<span>개인 <b>${(c.indiv*100).toFixed(1)}%</b> · 미확인 ${(c.unk*100).toFixed(1)}% · 실행 ${c.exec}MW</span></div>`;
  };
  document.getElementById('rank').innerHTML =
    rankable.slice(0, 40).map((p,i) => row(p,i)).join('')
    + (rankable.length > 40 ? `<div style="color:#888">… 외 ${rankable.length-40}지구</div>` : '');
  document.getElementById('unkSum').innerText =
    `소유 확인 필요 지구 (${flagged.length}개) — 미확인 >20%, 조사 시 승격 가능`;
  document.getElementById('unkList').innerHTML =
    flagged.sort((a,b) => b._c.unk - a._c.unk).map(p => row(p, null)).join('');
  document.querySelectorAll('.rk').forEach(el => el.onclick = () => {
    const p = mrgPolys.find(q => q._c.id == el.dataset.id);
    if (p) { map.fitBounds(p.getBounds().pad(0.4)); p.openPopup(); }
  });
  document.getElementById('longStat').innerHTML =
    `지름≥3km <b>${nd}</b>${hlDiam?' <span style="color:#d62728">■강조</span>':''} · `+
    `세장도≥6 <b>${ne}</b>${hlElong?' <span style="color:#e07b00">■강조</span>':''} (표시분 중)`;
}
refresh();
document.querySelectorAll('.mw').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.mw').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); minMW = parseFloat(b.dataset.v); refresh();});
document.getElementById('bDiam').onclick = e => {
  hlDiam = !hlDiam; e.target.classList.toggle('on'); refresh();};
document.getElementById('bElong').onclick = e => {
  hlElong = !hlElong; e.target.classList.toggle('on'); refresh();};
const tog = (btn, grp) => btn.onclick = e => {
  map.hasLayer(grp) ? map.removeLayer(grp) : grp.addTo(map);
  e.target.classList.toggle('on');};
tog(document.getElementById('bMrg'), gMrg);
tog(document.getElementById('bPre'), gPre);
tog(document.getElementById('bUn'), gUn);
</script></body></html>"""

ms = mrg["summary"].get("merge") or {}
C = SUMMARY
demand = (f"수요 {C['demand_gwh_3yr']:,}GWh/년 — S0 발전 {C['s0_gen_gwh']}GWh({C['s0_demand_pct']}%) · "
          f"S3 {C['s3_gen_gwh']}GWh({C['s3_demand_pct']}%)<br><span style='color:#888'>{C['demand_note']}</span>"
          ) if C.get("demand_gwh_3yr") else (
          f"S0 잠재 발전 <b>{C.get('s0_gen_gwh','?'):,}GWh/년</b> · S3 <b>{C.get('s3_gen_gwh','?'):,}GWh/년</b><br>"
          f"<span style='color:#b7791f'>시군 수요(한전 3개년) 수집 예정 — 확보 시 % 표기</span><br>"
          f"<span style='color:#888'>{C.get('demand_note','')}</span>")
dist = (f"중앙값 {C['dist_complex_median_km']}km · 최단 {C['dist_complex_min_km']}km"
        if C.get("dist_complex_median_km") is not None else "산정 예정")
cplx = ", ".join(C.get("main_complexes") or []) if C.get("complex_covered") \
       else "산정 예정 (산단 목록 확장 필요 — 시군 내 등재 산단 없음)"
html = (html
        .replace("__C_S0N__", f"{C.get('s0_n',0):,}").replace("__C_S0MW__", f"{C.get('s0_mw',0):,}")
        .replace("__C_S3N__", f"{C.get('s3_n',0):,}").replace("__C_S3MW__", f"{C.get('s3_mw',0):,}")
        .replace("__C_RATIO__", str(C.get("s3_over_s0", "?")))
        .replace("__C_DEMAND__", demand)
        .replace("__C_LN__", str(C.get("listed_n", 0))).replace("__C_LMW__", f"{C.get('listed_mw',0):,}")
        .replace("__C_SHARE__", str(C.get("listed_share_pct", "?")))
        .replace("__C_DIST__", dist).replace("__C_CPLX__", cplx)
        .replace("__C_PCT50__", str(C.get("pct_of_50mw", "?")))
        .replace("__C_STATUS__", str(C.get("designation_status", "?")))
        .replace("__C_T50__", str(C.get("threshold_t_50", "?")))
        .replace("__C_T100__", str(C.get("threshold_t_100", "?")))
        .replace("__C_OFFN__", str(C.get("official_n_ref", "?")))
        .replace("__C_OFFMW__", str(C.get("official_mw_ref", "?"))))
html = (html.replace("__NAME__", NAME)
        .replace("__R_LOCAL__", str(mrg["summary"].get("r_local_m", "?")))
        .replace("__N_MERGED__", str(ms.get("n_merged", 0)))
        .replace("__REJ_CAP__", str(ms.get("rejected_cap", 0)))
        .replace("__REJ_DIAM__", str(ms.get("rejected_diam", 0)))
        .replace("__N_PRE__", str(len(data["pre"])))
        .replace("__N_MRG__", str(len(data["mrg"])))
        .replace("__N_UN__", f"{len(un_pts):,}")
        .replace("__TOT_MW__", str(mrg["summary"].get("mw", "?")))
        .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
out_path = os.path.join(OUT, f"inspect_dangjin.html" if SGG == "44270" else f"inspect_{SGG}.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"저장: {out_path} ({os.path.getsize(out_path)/1e6:.1f} MB) / "
      f"병합후 {len(data['mrg'])} / 병합전 {len(data['pre'])} / 미편입 {len(un_pts):,}")
