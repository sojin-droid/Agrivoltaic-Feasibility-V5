# -*- coding: utf-8 -*-
"""자문(경기도) 후보 공간 전량 — 면적 문턱 없이 맥락 축·도형을 만든다 (2026-09-28 · 사용자 결정).

왜: block_context·analysis_unit_v1 은 min_area_m2 = 11,111㎡(≈0.5MW) 이상만 대상으로 만들어졌다.
    이 값은 설명할 근거가 없는 임의 문턱이라 자문 화면에서 뺀다. 21m 연접(후보 공간 생성) 자체에는
    원래 면적 문턱이 없다 — clusters.parquet 는 적격 필지 전량을 이은 결과다.

무엇을 하는가 (새 판정·새 21m·새 점수 없음)
  1) 맥락 축 — 정본 엔진 engine/block_context.py 의 build(run, take_all=True) 를 **코드 그대로** 호출한다.
     입력은 정본 런(scenario_runs/<run>)의 clusters·members·grid_link 에서 경기도에 필지가 하나라도 있는
     후보 공간만 골라(경계 걸침 단위의 도 밖 필지 포함) 별도 폴더에 둔 사본이다. 정본 런은 덮어쓰지 않는다.
  2) 도형(R2_promo) — v9_02_analysis_unit_polygon.py 와 같은 절차(지적 dissolve · 시군 걸침 합침 ·
     단순화 2 m 뒤 make_valid · 면적비 0.99–1.01 = default)를 같은 대상 방식으로 적용한다.
게이트(FAIL 시 중단)
  G1  11,111㎡ 이상 부분은 정본 block_context 와 값이 같다(lo·hi·산단 거리·대표점·간척 %) — 시군×단위 전수
  G2  11,111㎡ 이상 부분의 도형 면적·표시 등급은 analysis_unit_v1 과 같다
  G3  대상 단위 수 = 정본 members 에서 경기도 필지를 가진 단위 수
산출: Ledger_Rebuild/advisory_all_v1/<run>/block_context.parquet · R2_promo/units.gpkg · build.json
사용: python pipeline/export/build_advisory_all_v1.py
"""
import os, sys, json, time, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import MODEL, LR, CAD
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, MODEL)
import numpy as np, pandas as pd, duckdb, pyogrio, geopandas as gpd
from shapely import simplify, get_num_coordinates, union_all, make_valid
import engine.block_context as BC

SIDO, TOL, KW, OLD_MIN = '41', 2.0, 0.045, 11111.0
RUNS = ['R0_current', 'R2_promo', 'R3_zone_all']
SRC = os.path.join(LR, 'scenario_runs')
STAGE = os.path.join(LR, 'advisory_all_v1')
q = lambda p: str(p).replace('\\', '/')
con = duckdb.connect()
log = {'built_at': datetime.datetime.now().isoformat(timespec='seconds'), 'sido': SIDO, 'runs': {}}

# ── 1) 맥락 축 — 정본 엔진 그대로(take_all) ──
BC.RUNS = STAGE
for run in RUNS:
    src, dst = os.path.join(SRC, run), os.path.join(STAGE, run)
    os.makedirs(dst, exist_ok=True)
    labs = f"(SELECT DISTINCT lab FROM read_parquet('{q(src)}/members.parquet') WHERE pnu LIKE '{SIDO}%')"
    for f in ('clusters', 'members', 'grid_link'):
        con.execute(f"COPY (SELECT * FROM read_parquet('{q(src)}/{f}.parquet') WHERE lab IN {labs}) "
                    f"TO '{q(dst)}/{f}.parquet' (FORMAT PARQUET)")
    n_lab = con.execute(f"SELECT COUNT(*) FROM {labs}").fetchone()[0]
    n_cl = con.execute(f"SELECT COUNT(*) FROM read_parquet('{q(dst)}/clusters.parquet')").fetchone()[0]
    assert n_cl == n_lab, f'[FAIL] G3 {run}: clusters {n_cl} ≠ 경기도 관여 단위 {n_lab}'
    print(f"\n=== {run} · 경기도 관여 후보 공간 {n_lab:,} (정본 런에서 사본)", flush=True)
    BC.build(run, take_all=True)
    # G1 — 11,111㎡ 이상 부분은 정본 block_context 와 같아야 한다
    new = pd.read_parquet(os.path.join(dst, 'block_context.parquet'))
    old = pd.read_parquet(os.path.join(src, 'block_context.parquet'))
    old = old[old.lab.isin(set(new.lab))]
    m = old.merge(new, on=['lab', 'sgg'], how='left', suffixes=('_o', '_n'), indicator=True)
    assert (m['_merge'] == 'both').all(), f'[FAIL] G1 {run}: 정본 행 중 새 산출에 없는 (lab,sgg) {int((m._merge != "both").sum())}'
    for c in ('area_m2', 'lo', 'hi', 'dist_ind_km', 'x', 'y', 'reclaim_pct', 'n_emd', 'farm_ratio'):
        a, b = m[c + '_o'].to_numpy(float), m[c + '_n'].to_numpy(float)
        bad = ~((np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= 1e-6 * np.maximum(1, np.abs(a))))
        assert not bad.any(), f'[FAIL] G1 {run} {c}: {int(bad.sum())}행 불일치'
    n_small = int((new.drop_duplicates('lab').area_m2 < OLD_MIN).sum())
    print(f"G1 통과 — 11,111㎡ 이상 {m.lab.nunique():,}곳은 정본 값과 같음 · 새로 들어온 11,111㎡ 미만 {n_small:,}곳", flush=True)
    log['runs'][run] = {'n_unit': int(n_lab), 'n_unit_ge_11111': int(m.lab.nunique()), 'n_unit_lt_11111': n_small,
                        'n_block_sgg_pair': int(len(new))}

# ── 2) 도형(R2_promo) — v9_02 와 같은 절차 ──
run = 'R2_promo'; dst = os.path.join(STAGE, run)
mem = pd.read_parquet(os.path.join(dst, 'members.parquet'))[['pnu', 'lab']]
mem['sgg'] = mem.pnu.str[:5]; mem['emd8'] = mem.pnu.str[:8]
cl = pd.read_parquet(os.path.join(dst, 'clusters.parquet')).set_index('lab')
parts, miss_pnu, t0 = [], 0, time.time()
for s, sub in mem.groupby('sgg'):
    fp = os.path.join(CAD, f'{s}.gpkg')
    if not os.path.exists(fp):
        miss_pnu += len(sub); continue
    g = pyogrio.read_dataframe(fp, columns=['pnu']).merge(sub[['pnu', 'lab']], on='pnu', how='inner')
    miss_pnu += len(sub) - len(g)
    if len(g):
        parts.append(g.dissolve(by='lab')[['geometry']].reset_index())
P = pd.concat(parts, ignore_index=True)
dup = P.lab.duplicated(keep=False)
if dup.any():
    P = pd.concat([P[~dup], P[dup].groupby('lab')['geometry'].apply(lambda s: union_all(s.values)).reset_index()], ignore_index=True)
G = gpd.GeoDataFrame(P, geometry='geometry', crs='EPSG:5186')
G['area_geom_m2'] = G.area
G['geometry'] = simplify(G.geometry.values, TOL)
inv = ~G.geometry.is_valid
if inv.any():
    G.loc[inv, 'geometry'] = [make_valid(x) for x in G.loc[inv, 'geometry']]
agg = mem.groupby('lab').agg(n_parcel_geom=('pnu', 'size'), n_sgg=('sgg', 'nunique'), n_emd_geom=('emd8', 'nunique'))
agg['sgg_members'] = mem.groupby('lab').sgg.apply(lambda s: ','.join(sorted(set(s))))
agg['emd_members'] = mem.groupby('lab').emd8.apply(lambda s: ','.join(sorted(set(s))))
G = G.merge(agg, left_on='lab', right_index=True)
G['area_ledger_m2'] = G.lab.map(cl.area_m2)
G['mw_ref'] = (G.area_ledger_m2 * KW / 1000).round(3)
G['area_ratio'] = G.area_geom_m2 / G.area_ledger_m2
G['geom_quality'] = np.where(G.area_ratio < 0.99, 'geom_smaller', np.where(G.area_ratio > 1.01, 'geom_larger', 'ok'))
G['display_tier'] = np.where(G.geom_quality == 'ok', 'default', 'quality_review')
G['quality_label'] = G.geom_quality.map({'ok': '정상 기하', 'geom_smaller': '기하 불완전', 'geom_larger': '면적 불일치'})
missing = sorted(set(cl.index) - set(G.lab))
print(f"\n도형 {len(G):,} · 지적에서 못 찾은 필지 {miss_pnu:,} · 도형 없는 단위 {len(missing)} · {time.time() - t0:.0f}s", flush=True)
# G2 — 11,111㎡ 이상 부분은 analysis_unit_v1 과 같아야 한다
db = duckdb.connect(os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb'), read_only=True)
au = db.execute("SELECT lab, area_geom_m2, display_tier FROM analysis_unit_v1").fetch_df(); db.close()
cmp_ = au.merge(G[['lab', 'area_geom_m2', 'display_tier']], on='lab', suffixes=('_o', '_n'))
cmp_ = cmp_[cmp_.lab.isin(set(G.lab))]
d_rel = np.abs(cmp_.area_geom_m2_o - cmp_.area_geom_m2_n) / cmp_.area_geom_m2_o
assert (d_rel < 1e-6).all(), f'[FAIL] G2 도형 면적 불일치 {int((d_rel >= 1e-6).sum())}'
assert (cmp_.display_tier_o == cmp_.display_tier_n).all(), '[FAIL] G2 표시 등급 불일치'
print(f"G2 통과 — analysis_unit_v1 과 겹치는 {len(cmp_):,}곳의 도형 면적·표시 등급 같음", flush=True)
fo = os.path.join(dst, 'units.gpkg')
if os.path.exists(fo): os.remove(fo)
G.to_file(fo, layer='unit', driver='GPKG')
pd.DataFrame({'lab': missing, 'area_m2': [float(cl.area_m2[l]) for l in missing]}).to_parquet(os.path.join(dst, 'units_missing.parquet'), index=False)
log['geom'] = {'run': run, 'n_poly': int(len(G)), 'n_missing': len(missing), 'missing_parcels': int(miss_pnu), 'simplify_m': TOL,
               'tiers': {t: int((G.display_tier == t).sum()) for t in ('default', 'quality_review')}, 'g2_overlap': int(len(cmp_))}
log['rule'] = ('면적 문턱 없음 — 정본 런의 21m 후보 공간 중 경기도에 필지가 있는 것 전량. 맥락 축은 engine/block_context.build(take_all) 그대로, '
               '도형은 v9_02 절차 그대로. 11,111㎡ 이상 부분은 정본 값과 같음(G1·G2).')
json.dump(log, open(os.path.join(STAGE, 'build.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n완료', json.dumps(log, ensure_ascii=False))
