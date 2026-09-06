# -*- coding: utf-8 -*-
"""시군 브리프 생성기 (PR-0031 후속·야간 T3) — 209개 시군 × 1페이지 자족형 HTML.

지자체 담당자용: 그 시군의 공동 1등 구획(비지배 전선)·지산지소·열쇠 두 개 판독을
실명 데이터로. 전량 발행 데이터(recommend_v4·narrative_v4·sgg_matrix) 렌더 —
즉석 산정 없음. 출력: briefs/<sgg>.html + briefs/index.html (미추적 — 발행 결정 전).
"""
import gzip, json, os, html

SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(SITE, 'briefs')
os.makedirs(OUT, exist_ok=True)

def load(name):
    p = os.path.join(SITE, 'data_v4', name)
    if name.endswith('.gz'):
        return json.load(gzip.open(p, mode='rt', encoding='utf-8'))
    return json.load(open(p, encoding='utf-8'))

REC = load('recommend_v4.json.gz')
N = load('narrative_v4.json')
NAMES = load('sgg_matrix.json')['codes']
META = load('meta_v4.json')

ZONE = {'46820': '전남 해남', '44210': '충남 서산', '50110': '제주(도 전역)',
        '50130': '제주(도 전역)', '47111': '경북 포항', '47113': '경북 포항',
        '41430': '경기 의왕', '26140': '부산 서구', '31140': '울산 미포산단',
        '31170': '울산 미포산단'}
CP = {}
for b in N['cp_big']:
    CP.setdefault(b['sgg'], []).append(b)

nm = lambda s: NAMES.get(s, {}).get('name', s)
fmt = lambda v, d=1: ('—' if v is None else f'{v:,.{d}f}')

CSS = """
body{font-family:'Noto Sans KR',sans-serif;max-width:820px;margin:0 auto;padding:36px 22px;color:#16233A;line-height:1.7}
h1{font-family:Georgia,serif;font-size:26px;margin:0 0 4px} .sub{color:#6C757D;font-size:12.5px;margin-bottom:20px}
.kpi{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}
.kpi>div{border:1px solid #E3E6DC;border-radius:12px;padding:13px;text-align:center}
.kpi>div>b{display:block;font-family:Georgia,serif;font-size:27px;color:#16233A}
.kpi small{font-size:12px;color:#6C757D;font-weight:400}
.kpi span{font-size:11.5px;color:#6C757D}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
th,td{padding:6px 8px;border-bottom:1px solid #E3E6DC;text-align:right;white-space:nowrap}
th{color:#6C757D;font-size:11.5px} td.l,th.l{text-align:left}
.key{background:#F4F7F4;border:1px solid #C9D8BE;border-radius:10px;padding:12px 14px;font-size:13px;margin:14px 0}
.fn{font-size:11.5px;color:#6C757D;border-top:1px solid #E3E6DC;margin-top:22px;padding-top:10px}
h2{font-size:15px;margin:22px 0 6px}
"""

def brief(sgg, S):
    fr = S['frontier']
    if not fr:
        return None
    top = fr[0]
    tot_m2 = sum(p[0] for p in S.get('pts', [])) or None   # 시군 설치 가능 구획 총면적
    top_pct = (None if not tot_m2 else top['a'] / tot_m2 * 100)
    cp = CP.get(sgg, [])
    cp_mw = sum(b['mw'] for b in cp)
    zone = ZONE.get(sgg)
    ew = S.get('ew')
    ew_txt = (f" — 이 시군: 면적 {ew[0]}·계통 {ew[1]}·산단 {ew[2]}" if ew else "")
    dem = top.get('dem')
    dsh = top.get('dsh')
    dmf = top.get('dmf')
    rows = ''.join(
        f"<tr><td class='l'>{i+1}/{len(fr)}</td><td>{f['a']/1e6:,.3f}</td><td>{f['mw']}</td>"
        f"<td>{'알 수 없음' if f['lo'] is None else str(f['lo'])+('–'+str(f['hi']) if f['hi'] is not None else '')}</td>"
        f"<td>{'—' if f['d'] is None else f['d']}</td>"
        f"<td>{'—' if f.get('dsh') is None else str(f['dsh'])+'%'}</td>"
        f"<td>{f.get('wr', '—')}</td>"
        f"<td>{f['ra']}</td><td>{f['rl']}</td><td>{f['ri']}</td>"
        f"<td class='l'>{html.escape(f['strong'])}</td></tr>"
        for i, f in enumerate(fr[:10]))
    zline = (f"<b>{zone} — 제1차 분산에너지 특화지역</b>의 직접거래 특례(분산에너지법 §43)"
             if zone else "직접PPA 경로 — 발전 1MW 초과 · 전기사용자 300kW 이상")
    cpline = (f"이 시군의 특구급(≥50MW 등가) 후보 {len(cp)}곳 · 합 {cp_mw:,.0f}MW"
              if cp else "특구급(≥50MW 등가) 후보 없음 — 아래 공동 1등이 이 시군의 최대 구획")
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>{nm(sgg)} — 영농형 태양광 입지 브리프</title><style>{CSS}</style></head><body>
<h1>{nm(sgg)} — 영농형 태양광 입지 브리프</h1>
<div class="sub">PLANiT Institute · 전국 필지 전수 분석의 시군 절단면 · 데이터 {META.get('data_generation','')} ·
농업진흥구역 개방(재생에너지지구 지정) 가정 기준 — 개방 전 값은 본 사이트 근거 탭</div>
<div class="kpi">
  <div><b>{top['a']/1e6:,.3f}<small> km²</small></b><span>최대 구획(공동 1등 1번) · 참고 {top['mw']}MW{' · 간척 '+str(top['recl'])+'%' if (top.get('recl') or 0)>=50 else ''}<br>{'' if top_pct is None else f'= 시군 설치 가능 구획 총면적 {tot_m2/1e6:,.1f}km²의 <b>{top_pct:.0f}%</b>'}</span></div>
  <div><b>{'—' if dsh is None else str(dsh)}<small> %</small></b><span>시군 연간 전력사용량{'' if dem is None else f' {dem:,.0f}GWh'} 대비<br>이 구획의 참고 발전량</span></div>
  <div><b>{len(fr)}<small> 곳</small></b><span>세 축(규모·계통·거리) 비지배<br>공동 1등 구획 수</span></div>
</div>
<div class="key"><b>열쇠 두 개 판독</b><br>
① 부지 — 영농형태양광법 §6①2호 재생에너지지구 지정 시 위 구획이 열림 (현재 미지정 — 이 브리프가 그 근거 자료)<br>
② 판로 — {zline}{'' if dmf is None else f' · 시군 수요의 {dmf:.0f}%가 제조업'}</div>
<h2>공동 1등 구획 (면적순 표시 — 순위 아님)</h2>
<table><tr><th class='l'>번호</th><th>면적 km²</th><th>참고 MW</th><th>계통 여유 MW</th><th>산단 km</th><th>수요 대비</th><th>가중 순위(WPM·entropy)</th><th>면적 순위</th><th>계통 순위</th><th>산단 순위</th><th class='l'>강한 축</th></tr>{rows}</table>
<div style="font-size:11.5px;color:#6C757D;margin-top:2px">공동 1등 = 세 축(면적·계통 여유·산단 거리) <b>모두에서 자기를 이기는 구획이 시군 안에 하나도 없는</b> 구획 전원(비지배 집합).
축 1위들뿐 아니라, 어느 축도 1위가 아니지만 아무에게도 전패하지 않는 <b>타협형</b>이 포함되는 것이 이 방식의 본질 — "강한 축"은 그 구획이 가장 잘하는 축의 순위 표기이지 1위 표기가 아님.
가중 순위(WPM·entropy) = 가중곱(Bridgman 1922) × 시군별 엔트로피 가중(Shannon 1948{ew_txt})의 구획 전량 중 순위 — <b>변별력 가중(데이터 분포가 정함)이며 중요도 가중이 아님</b>(PR-0038). 병기 관점(ADR-0045)이며 어느 쪽도 단독 판정이 아님.</div>
<div style="font-size:12px;color:#6C757D">{cpline}</div>
<div class="fn">참고 환산 = 0.045 kW/㎡ · 발전량 = MW×1,314h(이용률 15% 가정) — 표기 전용, 판정·선별 불사용 ·
계통 여유 = 읍면동 균등배분 하한–상한(2026-07 스냅숏, 참고 표기) · 거리 = 측지 직선 ·
정본 출처·방법·한계: 사이트(입지 추천·방법·자료 탭) · 이 문서는 자동 생성본입니다.</div>
</body></html>"""

made, skipped = [], []
for sgg, S in sorted(REC['sgg'].items()):
    h = brief(sgg, S)
    if h is None:
        skipped.append(sgg); continue
    open(os.path.join(OUT, f'{sgg}.html'), 'w', encoding='utf-8').write(h)
    made.append(sgg)

idx_rows = ''.join(
    f"<tr><td class='l'><a href='{s}.html'>{nm(s)}</a></td>"
    f"<td>{REC['sgg'][s]['frontier'][0]['a']/1e6:,.3f} km²</td>"
    f"<td>{len(REC['sgg'][s]['frontier'])}</td>"
    f"<td>{'분산특구' if ZONE.get(s) else ''}</td></tr>"
    for s in made)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(
    f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>시군 브리프 색인</title><style>{CSS}</style></head><body>
<h1>시군 브리프 — {len(made)}개</h1>
<div class="sub">자동 생성 {META.get('generated','')} · 각 1페이지 = 그 시군의 공동 1등·지산지소·열쇠 판독</div>
<table><tr><th class='l'>시군</th><th>1등 구획 면적</th><th>공동 1등 수</th><th></th></tr>{idx_rows}</table>
</body></html>""")
print(f'브리프 {len(made)}개 생성 · 건너뜀 {len(skipped)} → {OUT}')
