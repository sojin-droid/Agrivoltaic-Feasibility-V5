# -*- coding: utf-8 -*-
"""시군별 대규모 후보 공간 수 export — 시나리오별 결과 화면의 "대규모 후보가 있는 시군" 목록용 (2026-09-28).

왜: 결과 화면이 "후보 필지 면적 상위 12곳"을 보여 줬는데 12라는 기준에 근거가 없었다. 전국 50MW 이상 후보 공간이
    어느 시군에 있는지를 **빠짐없이** 보여 주도록 바꾼다(사용자 지시 2026-09-28).
원천: 등재 런 8칸(R0~R3 × 이격 미적용/적용, 법인·국공유)의 scenario_runs/<런>/block_context.parquet — TOP 10 export 와 같은 입력.
      새 판정·새 문턱 없음. 50MW 등가 = 1,111,111 ㎡ · 3MW 등가 = 66,667 ㎡ (0.045 kW/㎡ 환산 읽기 눈금, 기존 값).
시군 귀속: touch — 시군 경계를 넘는 후보 공간은 관여한 시군마다 1로 센다(현재 8칸 모두 50MW 이상 걸침 0건).
게이트: 칸마다 50MW 이상 고유 후보 공간 수 = narrative_v4 ge50 · 3MW 이상 고유 수 = results_v4 size_bands. 어긋나면 쓰지 않는다.
산출: data_v4/big_sgg_v4.json  {runs: {run: {n50, n3, n_all, all_sgg: {sgg5: 전량}, sgg: {sgg5: [n50, km2_50, n3]}}}}
      sgg = 3MW 이상이 있는 시군 전부 · all_sgg = 문턱 없는 후보 공간 전량(시군 관여 기준)
사용: python pipeline/export/export_big_sgg_v4.py
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd

RUNS = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB', 'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
M2_50, M2_3 = 1111111.1, 66666.7
N = json.load(open(os.path.join(SITE, 'data_v4', 'narrative_v4.json'), encoding='utf-8'))['runs']
R = json.load(open(os.path.join(SITE, 'data_v4', 'results_v4.json'), encoding='utf-8'))['runs']
band = lambda run, ha: next((b for b in R[run].get('size_bands', []) if abs(b['min_ha'] - ha) < 0.01), None)

out, bad = {}, []
for run in RUNS:
    b = pd.read_parquet(os.path.join(LR, 'scenario_runs', run, 'block_context.parquet'), columns=['lab', 'sgg', 'area_m2'])
    # 전량(문턱 없음) — 시군에 필지가 하나라도 있는 21m 후보 공간 수(touch). block_context 의 11,111㎡ 하한과 무관하다.
    m = pd.read_parquet(os.path.join(LR, 'scenario_runs', run, 'members.parquet'), columns=['pnu', 'lab'])
    m['sgg'] = m.pnu.astype(str).str[:5]
    n_all_sgg = m.drop_duplicates(['lab', 'sgg']).groupby('sgg').lab.nunique()
    n_all = int(m.lab.nunique())
    b50, b3 = b[b.area_m2 >= M2_50], b[b.area_m2 >= M2_3]
    n50, n3 = int(b50.lab.nunique()), int(b3.lab.nunique())
    if n50 != N[run]['ge50']: bad.append(f'{run} 50MW {n50} ≠ narrative {N[run]["ge50"]}')
    if n_all != R[run]['n_component']: bad.append(f'{run} 전량 {n_all} ≠ results_v4 n_component {R[run]["n_component"]}')
    rb = band(run, 6.6667)
    if rb and n3 != rb['n']: bad.append(f'{run} 3MW {n3} ≠ results_v4 {rb["n"]}')
    g50 = b50.groupby('sgg').agg(n=('lab', 'nunique'), m2=('area_m2', 'sum'))
    g3 = b3.groupby('sgg').lab.nunique()
    # 3MW 이상이 하나라도 있는 시군 전부 — 50MW 이상 목록은 화면이 n50 > 0 으로 거른다
    out[run] = {'n50': n50, 'n3': n3, 'n_all': n_all, 'all_sgg': {k: int(v) for k, v in n_all_sgg.items()},
                'sgg': {s: [int(g50.n.get(s, 0)), round(float(g50.m2.get(s, 0)) / 1e6, 2), int(n)] for s, n in g3.sort_values(ascending=False).items()}}
    print(f'{run:16s} 50MW↑ {n50:>3}곳 · 시군 {len(g50):>2} · 3MW↑ {n3:>5}곳 · 시군 {len(g3):>3} · 전량 {n_all:>7,}')
if bad:
    raise SystemExit('[FAIL] 게이트 — 쓰지 않음: ' + ' · '.join(bad))
doc = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
       'source': 'scenario_runs/<run>/block_context.parquet (등재 런 8칸 · 법인·국공유)',
       'rule': '50MW 등가 = 1,111,111㎡ · 3MW 등가 = 66,667㎡ (0.045 kW/㎡ 읽기 눈금) · 시군 귀속 touch',
       'cols': ['n50', 'km2_50', 'n3'], 'all_sgg': '시군별 후보 공간 전량(문턱 없음 · members touch)', 'runs': out}
p = os.path.join(SITE, 'data_v4', 'big_sgg_v4.json')
json.dump(doc, open(p, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('written', p, os.path.getsize(p), 'bytes · 게이트 통과(8칸 모두 narrative·results_v4 와 일치)')
