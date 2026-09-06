# -*- coding: utf-8 -*-
"""잠재량 산정 큐브 export — data_v4/estimate_v4.json.gz (PR-0029 · 화면 '잠재량 산정').

전량 model/query.py 표준 질의(cube_data)에서만 산출. 게이트는 cube_data(verify=True)
내장 가산성 항등식 — 큐브 합산이 matrix_data 36칸(우주 3 × 모집단 3 × R0~R3 본값)을
정확 재현하지 못하면 여기서 중단된다.

담는 것:
  rows        칸 배열 [sgg, own, zone, sb, recl, n, m2] — zone/recl 은 사전 인덱스
  runs        등재 런 17종 요약(필지·면적·구획 수) — 조합이 등재 런과 일치할 때
              "정본 등재" 배지 + 2층(연접 구획) 값 표기용
  own_labels  소유 코드 라벨 (01~08 확립분만 이름, 나머지는 코드 그대로)
사용: python pipeline/export/export_estimate_v4.py
"""
import os
import sys
import json
import gzip
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, MODEL
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, MODEL)
import query as Q

cube = Q.cube_data(verify=True)                     # 가산성 게이트 내장 — FAIL 시 중단
print(f"큐브 {len(cube):,}칸")

ZONES = list(Q.CUBE_ZONES)                          # ['out','protect','promo']
RECLS = list(Q.CUBE_RECL)                           # ['none','etc','nat']
rows = [[c['sgg'], c['own'], ZONES.index(c['zone']), int(c['sb']),
         RECLS.index(c['recl']), c['n'], round(c['m2'])] for c in cube]

# 시군 라벨 (입지 추천 export 와 같은 출처)
sggs = sorted({c['sgg'] for c in cube})
labels = {g: Q._sgg_label(g) for g in sggs}

# 등재 런 요약 — 2층(연접 구획) 참조용. 큐브로는 구획을 만들 수 없다(τ 연접, PR-0029)
con = Q.db()
runs = {}
for name, ne, ek, nc, ck, mw in con.execute("""
    SELECT name, n_eligible, eligible_area_km2, n_component, component_area_km2, m_total_mw
    FROM scenario_runs WHERE theta_ha IS NULL""").fetchall():
    runs[name] = {'n': ne, 'km2': ek, 'n_comp': nc, 'comp_km2': ck, 'mw': mw}
con.close()
print(f"등재 런 {len(runs)}종")

OWN_LABELS = {'01': '개인', '02': '국유', '03': '외국인', '04': '시·도',
              '05': '군(郡)', '06': '법인', '07': '종중', '08': '종교단체'}

out = {'built': datetime.date.today().isoformat(),
       'method': '본값 = 실경작 무관 적격(경성 제약 통과, ADR-0039) · 면적이 정본, '
                 'MW 는 계수(기본 0.045 kW/㎡) 환산 참고 표기(ADR-0044 §3)',
       'gate': '가산성 항등식 — 큐브 합산이 matrix 36칸(우주 3×모집단 3×R0~R3 본값) 정확 재현',
       'zones': ZONES, 'recls': RECLS,
       'own_labels': OWN_LABELS,
       'coef_default': 0.045,
       'universes': {'pubcorp': ['02', '04', '05', '06'],
                     'pubcorp_clan': ['02', '04', '05', '06', '07', '08']},
       'sgg_labels': labels,
       'runs': runs,
       'rows': rows}
fo = os.path.join(SITE, 'data_v4', 'estimate_v4.json.gz')
with gzip.open(fo, 'wt', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
print(f"저장 {fo} — {os.path.getsize(fo)/1024:.0f} KB")
