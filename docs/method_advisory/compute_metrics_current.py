# -*- coding: utf-8 -*-
"""현재 21m 연접 단위(전량 · ≤1,000m 응축 없음)에 대한 평가 지표 — METRICS_DEFINITIONS.md 의 정의 그대로 (자문용 기술 통계).

2026-09 방법 비교(PR-0042)의 수치는 기준 방법 A 에 폐기된 1,000m 응축 층이 포함되어 있어 쓰지 않는다. 여기서는 같은 지표를
2026-10-07 전량 재산출된 analysis_unit_v1 / block_context(R2_promo) 위에서 다시 계산한다. 전국 + 검토 대상지 10곳(시군 관여 touch).
출력: docs/method_advisory/data/metrics_current_21m.csv · 화면·브리프 표의 원천.
"""
import os, sys, json, csv
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np, pandas as pd, duckdb, pyogrio, geopandas as gpd

LR = r'C:\Users\user\새 폴더\Ledger_Rebuild'
SITE = r'C:\Users\user\Agrivoltaic-V5'
RUN = os.path.join(LR, 'scenario_runs', 'R2_promo')
DB = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
GPKG = os.path.join(LR, 'analysis_units', 'analysis_unit_v1.gpkg')
SA = json.load(open(os.path.join(SITE, 'docs', 'method_advisory', 'study_areas.json'), encoding='utf-8'))['areas']
B = {'3MW': 66_667, '10MW': 222_222, '20MW': 444_444, '50MW': 1_111_111}

def gini(x):
    x = np.sort(np.asarray(x, float)); n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum())) if n and x.sum() > 0 else float('nan')

cl = pd.read_parquet(os.path.join(RUN, 'clusters.parquet'))[['lab', 'n_parcel', 'area_m2']]
bc = pd.read_parquet(os.path.join(RUN, 'block_context.parquet'))[['lab', 'sgg', 'n_emd', 'dist_ind_km']]
con = duckdb.connect(DB, read_only=True)
au = con.execute("SELECT lab, area_geom_m2, n_sgg, n_emd_geom FROM analysis_unit_v1").df()
print('units', len(cl), 'bc rows', len(bc), 'polygons', len(au), flush=True)
# 볼록껍질 채움 — 폴리곤이 있는 단위만 (장부 면적 ÷ 볼록껍질 면적, 1 이하만)
g = pyogrio.read_dataframe(GPKG, columns=['lab'])
g['hull_area'] = g.geometry.convex_hull.area
hull = g[['lab', 'hull_area']].set_index('lab')['hull_area']
U = cl.merge(au, on='lab', how='left')
U['has_geom'] = U.area_geom_m2.notna()
U['hull_fill'] = U.area_m2 / U.lab.map(hull)
nsgg = bc.groupby('lab').sgg.nunique(); U['n_sgg_touch'] = U.lab.map(nsgg).fillna(1)
nemd = bc.drop_duplicates('lab').set_index('lab').n_emd; U['n_emd'] = U.lab.map(nemd)
dist_ok = bc.drop_duplicates('lab').set_index('lab').dist_ind_km.notna(); U['dist_ok'] = U.lab.map(dist_ok).fillna(False)

def block(g):
    tot = float(g.area_m2.sum()); n = len(g); r = {}
    r['n_units'] = n; r['area_km2'] = round(tot / 1e6, 2)
    r['1a_share_ge20MW'] = round(float(g.loc[g.area_m2 >= B['20MW'], 'area_m2'].sum() / tot), 4)
    r['1a_share_ge50MW'] = round(float(g.loc[g.area_m2 >= B['50MW'], 'area_m2'].sum() / tot), 4)
    r['1b_top5_km2'] = round(float(g.area_m2.nlargest(5).sum() / 1e6), 2); r['1b_top25_km2'] = round(float(g.area_m2.nlargest(25).sum() / 1e6), 2)
    hf = g.loc[(g.n_parcel > 1) & g.hull_fill.notna() & (g.hull_fill <= 1.0), 'hull_fill']; r['1c_hull_fill_median'] = round(float(hf.median()), 3) if len(hf) else None
    r['2a_singleton_ratio'] = round(float((g.n_parcel == 1).mean()), 3)
    r['2b_share_lt3MW'] = round(float(g.loc[g.area_m2 < B['3MW'], 'area_m2'].sum() / tot), 4)
    r['2c_units_per_100km2'] = round(n / (tot / 1e8), 0)
    r['2d_area_gini'] = round(gini(g.area_m2), 3)
    for k, v in B.items(): r[f'3a_n_ge{k}'] = int((g.area_m2 >= v).sum())
    r['3c_chain_index'] = round(float(g.area_m2.max() / tot), 4)
    r['4a_has_geom_ratio'] = round(float(g.has_geom.mean()), 4)
    r['4b_multi_sgg_ratio'] = round(float((g.n_sgg_touch >= 2).mean()), 4)
    r['4c_n_emd_median'] = float(g.n_emd.median()) if g.n_emd.notna().any() else None
    r['4d_dist_computable_ratio'] = round(float(g.dist_ok.mean()), 4)
    return r

rows = [dict(scope='전국', name='전국', **block(U))]
for a in SA:
    labs = set(bc.loc[bc.sgg == a['sgg'], 'lab'])
    rows.append(dict(scope=a['sgg'], name=a['name'], **block(U[U.lab.isin(labs)])))
df = pd.DataFrame(rows)
keys = ['1a_share_ge20MW', '1c_hull_fill_median', '2a_singleton_ratio', '2b_share_lt3MW', '2c_units_per_100km2', '2d_area_gini', '3c_chain_index']
site = df[df.scope != '전국']
cv = {k: round(float(np.nanstd(site[k].astype(float)) / np.nanmean(site[k].astype(float))), 3) for k in keys}
df.loc[len(df)] = dict(scope='5a_cv', name='10곳 변동계수(5a)', **{k: cv.get(k) for k in df.columns if k not in ('scope', 'name')})
out = os.path.join(SITE, 'docs', 'method_advisory', 'data', 'metrics_current_21m.csv')
df.to_csv(out, index=False, encoding='utf-8-sig')
pd.set_option('display.width', 250); print(df.to_string(index=False)); print('saved', out)
