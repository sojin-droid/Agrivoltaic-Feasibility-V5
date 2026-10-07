# -*- coding: utf-8 -*-
"""기존 태양광 허가 주소 **필지 폴리곤** export — 클러스터링 자문 화면(③탭) 전용 · 검토 대상지 10곳.

원천: DuckDB existing_pv_parcel_v1(허가 자료 주소 → PNU · in_ledger) · Cadastre_All/{sgg}.gpkg(필지 형상) · ledger(지목·소유 구분)
  · 점(허가 주소 위치) 대신 그 주소 필지를 칠한다 — 한 발전소에 허가가 여럿이면 필지 하나에 기록 여러 건이 붙는다(n_records).
  · 표시만을 위한 자산이다. 기존 시설 × 후보 공간의 정본 중첩(PR-0049)과 무관하며 판정에 쓰지 않는다.
  · 지적도에서 찾지 못한 PNU 는 수로 남긴다(조용히 빼지 않음).
산출: data_v4/existing_parcels/{sgg}.json.gz (WGS84 · 속성 pnu · n · kind(p/y) · op(가동 중 수) · jimok · own · in_r2) · existing_parcels_index.json
사용: python pipeline/export/export_existing_parcels_v4.py
"""
import os, sys, json, gzip, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR, CAD
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import duckdb, pandas as pd, pyogrio, geopandas as gpd
from shapely.geometry import mapping

DB = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
MEM = os.path.join(LR, 'scenario_runs', 'R2_promo', 'members.parquet').replace(os.sep, '/')
SA = json.load(open(os.path.join(SITE, 'docs', 'method_advisory', 'study_areas.json'), encoding='utf-8'))['areas']
OUT = os.path.join(SITE, 'data_v4', 'existing_parcels'); os.makedirs(OUT, exist_ok=True)
con = duckdb.connect(DB, read_only=True)
idx = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'source': 'existing_pv_parcel_v1(2026-09-28) × Cadastre_All · 허가 주소 필지 · 표시 전용', 'sgg': {}}
for a in SA:
    s = a['sgg']
    P = con.execute(f"""
      SELECT p.pnu, COUNT(*) n, SUM(CASE WHEN p.pv_type LIKE '%영농%' THEN 1 ELSE 0 END) ny, SUM(CASE WHEN p.status_class='operating' THEN 1 ELSE 0 END) op,
             ANY_VALUE(l.category_name) jimok, ANY_VALUE(l.ownership_name) own, MAX(CASE WHEN m.pnu IS NOT NULL THEN 1 ELSE 0 END) in_r2
      FROM existing_pv_parcel_v1 p LEFT JOIN ledger l USING(pnu) LEFT JOIN (SELECT pnu FROM read_parquet('{MEM}')) m USING(pnu)
      WHERE p.pnu IS NOT NULL AND p.in_ledger AND substr(p.pnu,1,5)='{s}' GROUP BY p.pnu""").df()
    g = pyogrio.read_dataframe(os.path.join(CAD, f'{s}.gpkg'), columns=['pnu'])
    g = g.merge(P, on='pnu', how='inner').to_crs(4326)
    def rnd(c): return [rnd(x) if isinstance(x[0], (list, tuple)) else [round(x[0], 5), round(x[1], 5)] for x in c]
    feats = []
    for r in g.itertuples():
        gm = mapping(r.geometry); feats.append({'type': 'Feature', 'properties': {'pnu': r.pnu, 'n': int(r.n), 'kind': 'y' if r.ny else 'p', 'op': int(r.op), 'jimok': r.jimok, 'own': r.own, 'in_r2': int(r.in_r2)},
                                                 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}})
    with gzip.open(os.path.join(OUT, f'{s}.json.gz'), 'wt', encoding='utf-8') as fo:
        json.dump({'type': 'FeatureCollection', 'sgg': s, 'features': feats}, fo, ensure_ascii=False, separators=(',', ':'))
    jk = P.jimok.value_counts().head(5).to_dict(); ow = P.own.value_counts().head(5).to_dict()
    idx['sgg'][s] = {'name': a['name'], 'n_pnu': int(len(P)), 'n_records': int(P.n.sum()), 'n_geom': int(len(g)), 'n_missing_geom': int(len(P) - len(g)), 'in_r2': int(P.in_r2.sum()),
                     'farm_jimok': int(P.jimok.isin(['전', '답', '과수원']).sum()), 'indiv': int((P.own == '개인').sum()), 'jimok_top': jk, 'own_top': ow}
    print(f"{s} {a['name']}: PNU {len(P):,} (기록 {int(P.n.sum()):,}) · 폴리곤 {len(g):,} · 미발견 {len(P)-len(g)} · 전답과 {idx['sgg'][s]['farm_jimok']} · 개인 {idx['sgg'][s]['indiv']} · R2 후보 필지 {idx['sgg'][s]['in_r2']}", flush=True)
json.dump(idx, open(os.path.join(SITE, 'data_v4', 'existing_parcels_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved', OUT)
