# -*- coding: utf-8 -*-
"""우리 동네 TOP 10 — 시군별 후보 공간(21m 연접 단위) 전량 + 축 조합별 비지배 플래그 export (V5.5 · GGI 검토 반영).

무엇을 담는가 (data_v4/top10/{sgg}.json.gz, 시군당 1파일 · 8개 정본 정책 칸 전부):
  rows[]  그 시군에 관여하는 후보 공간(block_context 모집단 = 정본 그대로) 전량 —
          lab · 면적 ㎡ · 참고 MW · 계통 여유 lo/hi(소재 읍면동 하한/상한) · 최근접 산단 거리 km ·
          좌표(WGS84) · 간척 % · 필지 수 · 걸친 읍면동 수 · 비지배 플래그 4종 · 시군 전력판매량 대비 %(표기 전용)
  비지배 플래그: f3 = 3축(면적·계통·산단 — query._frontier_mask 와 동일) · fab = 면적+계통 · fac = 면적+산단 · fbc = 계통+산단
    - 2축 플래그는 3축과 **같은 규칙**(전수 쌍별 지배 비교, 결측 = 축 방향의 최악, 동률 ≠ 지배)을 축 부분집합에 적용한 것.
      새 점수·가중치·임계는 없다. 3축 플래그는 정본 함수(query._frontier_mask)로 재현 검증(G1)한다.
  단일 축 정렬은 화면에서 값 열을 정렬하는 보기 조작이며 여기서 만들지 않는다.

게이트(내장 · FAIL 시 산출 중단):
  G1  3축 플래그 = query._frontier_mask (시군·칸 전수)
  G2  export 행 수 = block_context 행 수 (시군·칸 전수) · 면적 합 일치
사용: python pipeline/export/export_top10_v4.py
"""
import os
import sys
import json
import gzip
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, MODEL, LR          # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, MODEL)
import numpy as np
import pandas as pd
from pyproj import Transformer
import query as Q

RUNS = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB',
        'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
COLS = ['lab', 'a', 'mw', 'lo', 'hi', 'd', 'lat', 'lon', 'recl', 'n', 'ne', 'f3', 'fab', 'fac', 'fbc', 'dsh']
FILTERS = [0, 66667, 222222, 444444, 1111111]     # 표시 규모 선택지(㎡) — UI 와 동일
AX = {'a': ('area_m2', +1), 'b': ('lo', +1), 'c': ('dist_ind_km', -1)}   # 방향: +1 최대화 · -1 최소화


def nondominated(d, axes):
    """전수 쌍별 지배 비교 — query._frontier_mask 와 같은 규칙을 축 부분집합에 적용.
    결측은 축 방향의 최악(최대화 -inf · 최소화 +inf), 동률은 지배가 아니다."""
    cols = [AX[k] for k in axes]
    v = np.column_stack([d[c].to_numpy(float) for c, _ in cols]).astype(float)
    for j, (_, sgn) in enumerate(cols):
        v[:, j] = np.nan_to_num(v[:, j], nan=(-np.inf if sgn > 0 else np.inf)) * sgn
    dom = np.zeros(len(v), dtype=bool)
    for i in range(len(v)):
        dom[i] = bool((np.all(v >= v[i], axis=1) & np.any(v > v[i], axis=1)).any())
    return ~dom


T = Transformer.from_crs(5186, 4326, always_xy=True)
dem, derr = Q._demand_load()                     # 지산지소 대조 — 표기 전용 (PR-0030)
if derr:
    print(f"  [주의] 수요 미로드 — dsh 는 null: {derr}")

out_dir = os.path.join(SITE, 'data_v4', 'top10')
os.makedirs(out_dir, exist_ok=True)
per_sgg = {}          # sgg → {run: {n, rows}}
labels = {}
stamps = {}
n_g1 = 0
for run in RUNS:
    got, err = Q._rec_load(run)
    assert not err, f"[FAIL] {err}"
    df, st = got
    stamps[run] = {'generated_at': st.get('generated_at'), 'grid_asset': (st.get('grid_asset') or {}).get('meta_built'),
                   'n_component_total': (st.get('subset') or {}).get('n_component_total')}
    lon, lat = T.transform(df['x'].to_numpy(float), df['y'].to_numpy(float))
    df = df.assign(lon=lon, lat=lat)
    for sgg, d in df.groupby('sgg'):
        d = d.sort_values('area_m2', ascending=False).reset_index(drop=True)
        f3 = nondominated(d, 'abc')
        # G1 — 정본 함수와 동일한지 재현
        ref = Q._frontier_mask(d)
        assert np.array_equal(f3, ref), f"[FAIL] G1 {run} {sgg}: 3축 플래그 ≠ query._frontier_mask"
        n_g1 += 1
        fab, fac, fbc = nondominated(d, 'ab'), nondominated(d, 'ac'), nondominated(d, 'bc')
        t = dem.get(sgg) if dem else None
        t_gwh = (None if t is None or pd.isna(t.total_gwh_year) else float(t.total_gwh_year))
        rows = []
        for i, r in d.iterrows():
            nz = lambda v, k: None if pd.isna(v) else round(float(v), k)
            has_xy = not (pd.isna(r['lon']) or pd.isna(r['lat']))
            rows.append([int(r['lab']), round(float(r['area_m2'])), round(float(r['mw']), 1),
                         nz(r['lo'], 1), nz(r['hi'], 1), nz(r['dist_ind_km'], 2),
                         (round(float(r['lat']), 5) if has_xy else None), (round(float(r['lon']), 5) if has_xy else None),
                         nz(r['reclaim_pct'], 0), int(r['n_parcel']), int(r['n_emd']) if not pd.isna(r['n_emd']) else None,
                         bool(f3[i]), bool(fab[i]), bool(fac[i]), bool(fbc[i]),
                         (None if not t_gwh else round(float(r['mw']) * Q.HOURS / 1000 / t_gwh * 100, 2))])
        # G2 — 발행 = 모집단
        assert len(rows) == len(d) and abs(sum(x[1] for x in rows) - round(float(d['area_m2'].sum()))) <= len(d), \
            f"[FAIL] G2 {run} {sgg}: 행 수/면적 합 불일치"
        # 표시 규모별 비지배 집합 — 비교 모집단 = 그 규모 이상 후보 전량(recommend_cc 의 by_filter 규약과 동일). 정본 함수와 대조(G1)
        fronts = {}
        for th in FILTERS:
            sub = d[d['area_m2'] >= th].reset_index(drop=True)
            if not len(sub): fronts[str(th)] = {'f3': [], 'fab': [], 'fac': [], 'fbc': []}; continue
            fr = {k: [int(x) for x in sub['lab'][nondominated(sub, a)]] for k, a in [('f3', 'abc'), ('fab', 'ab'), ('fac', 'ac'), ('fbc', 'bc')]}
            assert set(fr['f3']) == set(int(x) for x in sub['lab'][Q._frontier_mask(sub)]), f'[FAIL] G1 {run} {sgg} @{th}: 부분집합 3축 ≠ query._frontier_mask'
            fronts[str(th)] = fr
        per_sgg.setdefault(sgg, {})[run] = {'n': len(rows), 'n_f3': int(f3.sum()), 'rows': rows, 'fronts': fronts}
        labels[sgg] = Q._sgg_label(sgg)
print(f"G1 통과 — 3축 플래그 = 정본 함수 ({n_g1:,} 시군×칸) · G2 통과")

idx = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'runs': RUNS, 'cols': COLS,
       'population': 'block_context 모집단(정본 그대로 · 규모 문턱 없음) — 시군 관여 기준(걸침 후보는 관련 시군마다 등장, 합산 금지)',
       'fronts': '표시 규모(0·66667·222222·444444·1111111㎡)별 비지배 lab 목록 — 비교 모집단 = 그 규모 이상 전량',
       'flags': {'f3': '면적·계통 여유(lo)·산단 거리 3축 비지배 = query._frontier_mask', 'fab': '면적+계통 2축 비지배(같은 규칙)',
                 'fac': '면적+산단 2축 비지배(같은 규칙)', 'fbc': '계통+산단 2축 비지배(같은 규칙)'},
       'dsh': 'MW×1,314h ÷ 시군 연간 전력판매량(GWh) % — 표기 전용(PR-0030), 판정 불사용',
       'stamps': stamps, 'sgg': {}}
tot = 0
for sgg, runs in per_sgg.items():
    with gzip.open(os.path.join(out_dir, f'{sgg}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump({'sgg': sgg, 'label': labels[sgg], 'cols': COLS, 'runs': runs}, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    idx['sgg'][sgg] = {'label': labels[sgg], **{r: [v['n'], v['n_f3']] for r, v in runs.items()}}
    tot += os.path.getsize(os.path.join(out_dir, f'{sgg}.json.gz'))
json.dump(idx, open(os.path.join(SITE, 'data_v4', 'top10_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"저장 data_v4/top10/ — 시군 {len(per_sgg)} · {tot/1024/1024:.1f} MB · index top10_index.json")
