# -*- coding: utf-8 -*-
"""09b_inspect_index.py — 검수 지도 목록 페이지 (pipeline_out/inspect_index.html)"""
import os, sys, io, json, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
NAMES = {"44270": "당진", "44180": "보령", "44200": "아산", "44131": "천안동남",
         "44133": "천안서북", "44210": "서산", "44800": "홍성", "41590": "화성",
         "41220": "평택", "41463": "용인기흥", "41271": "안산상록", "41390": "시흥",
         "41500": "이천", "41480": "파주", "41570": "김포",
         "44810": "예산", "41461": "용인처인", "41465": "용인수지", "41273": "안산단원"}

SWEEP = json.load(open(os.path.join(OUT, "ownership_sweep_summary.json"), encoding="utf-8")) \
    if os.path.exists(os.path.join(OUT, "ownership_sweep_summary.json")) else {}
BADGE = {"유력": ("#276749", "#c6f6d5"), "지정 가능": ("#975a16", "#fefcbf"),
         "요건 미달": ("#9b2c2c", "#fed7d7")}

rows = []
for f in sorted(glob.glob(os.path.join(OUT, "clusters", "*_clusters_S3_t30_merged.json"))):
    sgg = os.path.basename(f)[:5]
    j = json.load(open(f, encoding="utf-8"))
    s = j["summary"]
    page = "inspect_dangjin.html" if sgg == "44270" else f"inspect_{sgg}.html"
    if not os.path.exists(os.path.join(OUT, page)):
        continue
    rows.append((sgg, NAMES.get(sgg, sgg), page, s))

rows.sort(key=lambda r: -SWEEP.get(r[0], {}).get("b_mw_t30", 0))
cells = []
for sgg, nm, page, s in rows:
    ms = s.get("merge") or {}
    sw = SWEEP.get(sgg, {})
    st = sw.get("status_t30", "?")
    fg, bg = BADGE.get(st, ("#555", "#eee"))
    cells.append(f"""<tr>
 <td><a href="{page}"><b>{nm}</b></a> <span style="color:#888">{sgg}</span></td>
 <td><span style="color:{fg};background:{bg};padding:1px 7px;border-radius:9px;font-weight:bold">{st}</span></td>
 <td><b>{sw.get('b_mw_t30','-')}</b></td>
 <td>{sw.get('threshold_t_50','-')} / {sw.get('threshold_t_100','-')}</td>
 <td>{s.get('n_clusters_official','-')} / {s.get('mw_official','-')}</td>
 <td>{s['n_clusters']:,} / {s['mw']:,.0f}</td>
 <td>{s['r_local_m']}m</td><td>{ms.get('n_merged','-')}(횡단거부 {ms.get('rejected_cross','-')})</td>
 <td>{s['n_leftover']:,}</td></tr>""")

html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>검수 지도 목록 — 후보지구 (S3 t0.30, P95 병합)</title>
<style>body{{font-family:'Malgun Gothic',sans-serif;max-width:960px;margin:24px auto;font-size:14px}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:5px 8px;text-align:right}}
td:first-child,th:first-child{{text-align:left}}
.warn{{background:#fff3cd;border:1px solid #ffc107;padding:6px 10px;border-radius:4px}}</style></head><body>
<h2>검수 지도 목록 — 시군별 후보지구 (S3 · t=0.30 · P95 병합)</h2>
<div class="warn">내부 검수 전용 — P95 병합 <b>추인 대기</b> / 세장형 <b>미결</b>. 배포 금지<br>
공식 지구 = <b>최대 연접 블록 ≥3MW</b>(접합 25m) · 특구 판정 = 공식∧미확인≤20% 합산:
<b>&lt;50MW 미달 / 50–100 지정 가능 / ≥100 유력</b> · 병합은 하천·철도 횡단 금지(2026-07-15)</p></div>
<p>지구 클릭 → 시군 지도. 각 지도: 병합 전/후(필지 union 표시), 하한 필터, 세장형 강조, 미편입,
우선 검토 순위(개인소유 낮은 순·미확인 분리).</p>
<table>
<tr><th>시군</th><th>특구 판정<br>(t=0.30)</th><th>실행가능 MW<br>(공식∧미확인≤20%)</th>
<th>문턱 t<br>(50 / 100MW)</th><th>공식 지구<br>(블록≥3MW) n/MW</th><th>전체 지구 n/MW</th>
<th>P95 r</th><th>병합(횡단거부)</th><th>미편입</th></tr>
{''.join(cells)}
</table>
<p style="color:#666">생성: 09b_inspect_index.py · 클러스터: 04_cluster.py (S3, t=0.30, --merge, --local)</p>
</body></html>"""
with open(os.path.join(OUT, "inspect_index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print(f"inspect_index.html — {len(rows)}개 시군 수록")
