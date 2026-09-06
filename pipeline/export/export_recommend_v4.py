# -*- coding: utf-8 -*-
"""시군별 공동 1등(3축 비지배 전선) export — data_v4/recommend_v4.json.gz (PR-0029).

전량 model/query.py 표준 질의(sgg_recommend_data)에서만 산출 — 즉석 전선 계산 금지.
게이트(내장, FAIL 시 산출 중단):
  G1 전선 항등식 — 멤버 상호 무지배 · 각 축 사전식 최적이 전선에 실재 (T19 재현)
  G2 export 행 수·면적 합 = 질의 산출과 정확 일치 (발행의 질의 우회 감지)

담는 것(시군당):
  frontier[]  공동 1등 전원 — 좌표(WGS84)·3축 값·축별 순위 3독립 컬럼·강한 축·
              확인용(경작·간척%)·판독기 사전계산(반경 2~12km 의 산단 점수 합·
              여유 합[배전선로 단위 중복 제거, MW])
  pts[]       산점도용 전 구획 3축 값 + 전선 플래그 (지배점 회색 표시용 — 숨은 배제 금지)
  r_default   기본 반경 = 그 시군 구획 p75 반올림(클립 2~12) — ADR/PR-0029 확정
  control     @all(개인 포함) 최대 구획 면적 — 제2조 병기

사용: python pipeline/export/export_recommend_v4.py
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
import geopandas as gpd
import shapely
import query as Q

RUN = 'R2_promo'
RADII = list(range(2, 13))                              # 판독기 눈금 2~12 km
SCORE = {'국가산업단지': 4, '일반산업단지': 3, '도시첨단산업단지': 2, '농공단지': 1}

# ── 표준 질의 산출 ──
d = Q.sgg_recommend_data(RUN)
assert not d['missing'], f"[FAIL] 대조군/정본 미산출: {d['missing']}"
rows = pd.DataFrame(d['rows'])
summ = {x['sgg']: x for x in d['sgg_summary']}
ctl = {c['sgg']: c for c in d['control_rows']}
print(f"질의 산출 — 전선 {len(rows):,}행 · 시군 {rows['sgg'].nunique()}")

# ── 구획 좌표·전 구획 3축 (산점도용) — 질의와 같은 자산에서 ──
got, err = Q._rec_load(RUN)
assert not err, err
bc, _st = got
u = bc.drop_duplicates('lab').set_index('lab')
g84 = gpd.GeoSeries(shapely.points(u['x'].to_numpy(float), u['y'].to_numpy(float)),
                    index=u.index, crs=5186).to_crs(4326)

# ── G1: 전선 항등식 재현 (질의 구현과 독립 코드로) ──
for sgg, grp in bc.groupby('sgg'):
    grp = grp.reset_index(drop=True)
    v = np.nan_to_num(np.array(grp[['area_m2', 'lo', 'dist_ind_km']].to_numpy(float),
                               copy=True), nan=-np.inf)
    v[:, 2] = -v[:, 2]
    dom = np.array([bool((np.all(v >= v[i], axis=1) & np.any(v > v[i], axis=1)).any())
                    for i in range(len(v))])
    q_labs = set(rows[rows['sgg'] == sgg]['lab'])
    e_labs = set(grp['lab'][~dom])
    assert q_labs == e_labs, f"[FAIL] G1 {sgg}: 질의 전선 ≠ 재현 전선"
print("G1 통과 — 전선 항등식 209개 시군 재현 일치")

# ── 판독기 사전계산 (전선 구획만 — 1,477개) ──
dan = gpd.read_file(os.path.join(LR, 'sources', 'ind_complex', 'damdan.gpkg')) \
         .drop_duplicates('dan_id').to_crs(5186)
w = dan['cat_nam'].map(SCORE).to_numpy(float)
con = Q.db()
# 여유 합 = 읍면동 균등배분 하한(lo) 합 — 균등배분은 전국 합 보존(64,020MW 실측
# 일치)이라 동 단위 합산에 설비 이중계상이 없다. DL vol_min 합은 부적합: 변형 간
# 최솟값이라 포화 변형이 하나라도 있으면 0으로 붕괴 (해남 실측 2026-09-01)
emd_lo = con.execute("SELECT emd8, vol3_equal_mw FROM grid_emd_v3 WHERE status='ok'")             .fetch_df().set_index('emd8')['vol3_equal_mw']
con.close()
emd = gpd.read_file(os.path.join(LR, 'sources', 'emd_bnd', 'emd_bnd.gpkg')).to_crs(5186)
emd['emd8'] = emd['emd_cd'].astype(str).str[:8]
# 신·구 행정코드 다리 — 경계(신 코드)에 없는 구 계통 코드를 이름·공간 대조로 연결
# (광주·전남 '12' 통합 등 — 다리 없이는 해남 등 신코드 지역의 여유 합이 0으로 붕괴)
from emd_alias import build_alias
_c = Q.db()
_alias = build_alias(_c, emd, set(emd_lo.index))
_c.close()
print(f"코드 다리 {len(_alias):,}건 (신 경계 → 구 계통)")
emd['lo'] = [emd_lo.get(c, emd_lo.get(_alias.get(c))) for c in emd['emd8']]
from shapely.strtree import STRtree
etree = STRtree(emd.geometry.values)

flabs = rows['lab'].unique()
fpts = shapely.points(u.loc[flabs, 'x'].to_numpy(float), u.loc[flabs, 'y'].to_numpy(float))
D = np.array([shapely.distance(dan.geometry.values, p) for p in fpts]) / 1000.0
reader = {}
for i, lab in enumerate(flabs):
    p = fpts[i]
    cand = etree.query(shapely.buffer(p, (RADII[-1] + 0.5) * 1000))
    ed = shapely.distance(emd.geometry.values[cand], p) / 1000.0
    elo = emd['lo'].values[cand].astype(float)
    sc, gr = [], []
    for r in RADII:
        sc.append(int(w[D[i] <= r].sum()))
        gr.append(round(float(np.nansum(elo[ed <= r])), 1))
    reader[int(lab)] = {'score': sc, 'grid': gr}
print(f"판독기 사전계산 — 전선 구획 {len(flabs):,} × 반경 {len(RADII)}눈금")

_n = lambda v: None if pd.isna(v) else float(v)
_r = lambda v, k: None if pd.isna(v) else round(float(v), k)

# ── 시군별 조립 ──
sggs = {}
for sgg, grp in rows.groupby('sgg'):
    all_b = bc[bc['sgg'] == sgg]
    nd = all_b['dist_ind_km'].to_numpy(float)
    r_def = int(np.clip(round(np.nanpercentile(nd, 75)), RADII[0], RADII[-1]))
    fr = []
    for _, r in grp.sort_values('area_m2', ascending=False).iterrows():
        lab = int(r['lab'])
        pt = g84.loc[lab]
        has_xy = not (pd.isna(pt.x) or pd.isna(pt.y))   # 지오메트리 결손 필지뿐인 구획
        fr.append({'lab': lab,
                   'lon': (round(pt.x, 5) if has_xy else None),
                   'lat': (round(pt.y, 5) if has_xy else None),
                   'a': round(float(r['area_m2'])), 'mw': round(float(r['mw']), 1),
                   # DataFrame 이 None 을 NaN 으로 바꾸므로 되돌린다 (결손 = null 표기)
                   'lo': _r(r['lo'], 1), 'hi': _r(r['hi'], 1),
                   'd': _r(r['dist_ind_km'], 2),
                   'ra': int(r['r_area']), 'rl': int(r['r_lo']), 'ri': int(r['r_ind']),
                   'strong': r['strong'], 'farm': _n(r['farm_ratio']),
                   'recl': _n(r['reclaim_pct']),
                   # 지산지소 대조 — 표기 전용 (query 산출 그대로, 판정 불사용)
                   'wr': int(r['wpm_rank']),   # 가중 병기 순위 (ADR-0045 개정 — WPM×entropy, 전량 중)
                   'dem': _r(r['demand_gwh'], 0), 'dsh': _r(r['demand_share_pct'], 1),
                   'dmf': _r(r['demand_manuf_pct'], 0),
                   'dsc': (None if (pd.isna(r['demand_scope']) or not r['demand_scope'])
                           else str(r['demand_scope'])),
                   # 좌표 결손이면 판독기도 결손 표기 — 0으로 가장하지 않는다
                   'reader': (reader[lab] if has_xy else None)})
    pts = [[round(float(a)), (None if pd.isna(l) else round(float(l), 1)),
            (None if pd.isna(dd) else round(float(dd), 2)), int(lb) in {f['lab'] for f in fr}]
           for a, l, dd, lb in zip(all_b['area_m2'], all_b['lo'],
                                   all_b['dist_ind_km'], all_b['lab'])]
    c = ctl.get(sgg)
    # 방법별 top-10 (PR-0036 10방법, 동일 가중) — §5 방법 선택기용. 표시 전용.
    mc = Q.sgg_mcdm_data(sgg, run=RUN, top=10, check_dominance=False)
    mtop = ({name: [t['lab'] for t in r['top']] for name, r in mc['methods'].items()}
            if 'error' not in mc else {})
    sggs[sgg] = {'label': Q._sgg_label(sgg), 'r_default': r_def,
                 'n_block': summ[sgg]['n_block'], 'n_pairs': summ[sgg]['n_pairs'],
                 'ew': summ[sgg].get('entropy_w'),   # 시군별 엔트로피 가중 (ADR-0045 개정)
                 'frontier': fr, 'pts': pts, 'mtop': mtop,
                 'control_max_m2': (round(float(c['area_m2'])) if c else None)}

# ── G2: 발행 = 질의 (행 수·면적 합 정확 일치) ──
n_exp = sum(len(s['frontier']) for s in sggs.values())
a_exp = sum(f['a'] for s in sggs.values() for f in s['frontier'])
a_qry = round(rows['area_m2'].sum())
assert n_exp == len(rows) and abs(a_exp - a_qry) <= len(rows), \
    f"[FAIL] G2 발행 ≠ 질의: 행 {n_exp}/{len(rows)} · 면적 {a_exp}/{a_qry}"
print(f"G2 통과 — 발행 {n_exp:,}행 = 질의 {len(rows):,}행")

out = {'run': RUN, 'built': datetime.date.today().isoformat(),
       'method': '3축 비지배(면적·계통 여유 lo·산단 거리) — 가중치·순서·관문 없음 (ADR-0044)',
       'score_def': SCORE,
       'reader_radii_km': RADII,
       'r_default_rule': '그 시군 구획의 최근접 산단 거리 p75 반올림 (클립 2~12km) — '
                         '고정 7km는 149개 시군 검정에서 51곳 변질로 기각(PR-0029)',
       'stamp': {'grid_link': _st.get('grid_link'), 'assets': _st.get('assets')},
       'sgg': sggs}
fo = os.path.join(SITE, 'data_v4', 'recommend_v4.json.gz')
with gzip.open(fo, 'wt', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
print(f"저장 {fo} — {os.path.getsize(fo)/1024:.0f} KB · 시군 {len(sggs)}")
