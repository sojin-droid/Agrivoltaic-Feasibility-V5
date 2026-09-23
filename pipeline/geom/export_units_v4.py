# -*- coding: utf-8 -*-
"""21m 공간 분석 단위(후보 공간) 폴리곤 export — data_v4/units/{sgg}.json.gz · data_v4/units_big.json.gz (V5.5).

원천: Ledger_Rebuild/analysis_units/analysis_unit_v1.gpkg (model/stages/v9_02_analysis_unit_polygon.py · 2026-09-23)
  = 기존 21m membership(R2_promo · PAPER-FREEZE-001 = production 동일 산출)을 지적 폴리곤에 dissolve 한 것.
  · cluster 가 아니다 — 최종 cluster 정의는 자문 이후로 열어 둔다.
  · 시군·읍면동 경계로 자르지 않는다 — 경계를 넘는 단위는 하나로 유지한다(관여 시군마다 같은 기하가 실린다).
  · 모집단 = block_context 선언 파라미터 min_area_m2 = 11,111 (숨은 문턱 없음) · 단순화 2 m(선언값).
여기서는 좌표계 변환(EPSG:5186 → WGS84)과 좌표 반올림(1e-5도 ≈ 1 m)만 한다 — 새 기하 연산·재클러스터링 없음.

속성: id(lab) · a(장부 면적 ㎡) · mw(참고) · n(필지) · ns(관여 시군 수) · sggs · ne(읍면동 수) · emds · q(기하 품질) · ag(기하 면적 ㎡)
게이트: 폴리곤 수 = DuckDB analysis_unit_v1 행 수 · lab 집합 일치 · 면적 합 일치.
사용: python pipeline/geom/export_units_v4.py
"""
import os, sys, json, gzip, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import duckdb, pyogrio, geopandas as gpd
from shapely.geometry import mapping

GPKG = os.path.join(LR, 'analysis_units', 'analysis_unit_v1.gpkg')
DB = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
BIG_M2 = 1_111_111          # 약 50MW 등가 읽기 눈금 (results_v4 size_bands min_ha 111.1111 과 동일)

layers = pyogrio.list_layers(GPKG)
print('layers:', layers.tolist() if hasattr(layers, 'tolist') else layers)
g = gpd.read_file(GPKG, layer=layers[0][0])
print(f"gpkg {len(g):,} polygons · crs {g.crs} · cols {list(g.columns)}")
con = duckdb.connect(DB, read_only=True)
attr = con.execute("SELECT lab, area_ledger_m2, mw_ref, n_parcel_geom, n_sgg, sgg_members, n_emd_geom, emd_members, geom_quality, area_geom_m2 FROM analysis_unit_v1").fetch_df()
con.close()
assert len(g) == len(attr) and set(g['lab'].astype(int)) == set(attr['lab'].astype(int)), '[FAIL] gpkg ≠ analysis_unit_v1 (행 수/lab 집합)'
g = g[['lab', 'geometry']].merge(attr, on='lab')
g84 = g.to_crs(4326)

def rnd(coords):
    return [rnd(c) if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)] for c in coords]

def feat(r):
    gm = mapping(r.geometry)
    gm = {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}
    p = {'id': int(r.lab), 'a': round(float(r.area_ledger_m2)), 'mw': round(float(r.mw_ref), 1), 'n': int(r.n_parcel_geom),
         'ns': int(r.n_sgg), 'sggs': str(r.sgg_members).split(','), 'ne': int(r.n_emd_geom), 'emds': str(r.emd_members).split(','),
         'q': str(r.geom_quality), 'ag': round(float(r.area_geom_m2))}
    return {'type': 'Feature', 'properties': p, 'geometry': gm}

feats = [feat(r) for r in g84.itertuples()]
by_sgg = {}
for f in feats:
    for s in f['properties']['sggs']:
        by_sgg.setdefault(s, []).append(f)
out_dir = os.path.join(SITE, 'data_v4', 'units'); os.makedirs(out_dir, exist_ok=True)
tot = 0; idx = {}
for s, fs in by_sgg.items():
    fs = sorted(fs, key=lambda f: -f['properties']['a'])
    with gzip.open(os.path.join(out_dir, f'{s}.json.gz'), 'wt', encoding='utf-8') as fo:
        json.dump({'type': 'FeatureCollection', 'sgg': s, 'run': 'R2_promo', 'features': fs}, fo, ensure_ascii=False, separators=(',', ':'))
    tot += os.path.getsize(os.path.join(out_dir, f'{s}.json.gz'))
    idx[s] = {'k': len(fs), 'km2': round(sum(f['properties']['a'] for f in fs) / 1e6, 2), 'cross': sum(1 for f in fs if f['properties']['ns'] > 1)}
big = sorted([f for f in feats if f['properties']['a'] >= BIG_M2], key=lambda f: -f['properties']['a'])
with gzip.open(os.path.join(SITE, 'data_v4', 'units_big.json.gz'), 'wt', encoding='utf-8') as fo:
    json.dump({'type': 'FeatureCollection', 'run': 'R2_promo', 'min_m2': BIG_M2, 'features': big}, fo, ensure_ascii=False, separators=(',', ':'))
a_sum = sum(f['properties']['a'] for f in feats)
assert abs(a_sum - round(float(attr['area_ledger_m2'].sum()))) <= len(feats), '[FAIL] 면적 합 불일치'
json.dump({'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'source': 'analysis_unit_v1.gpkg (v9_02 · 2026-09-23) · R2_promo · min_area_m2 11,111 · simplify 2 m',
           'n_units': len(feats), 'n_big': len(big), 'n_cross_sgg': sum(1 for f in feats if f['properties']['ns'] > 1), 'unit_note': '21m 연접 공간 분석 단위 — cluster 아님(최종 정의 자문 전) · 경계로 자르지 않음',
           'sgg': idx}, open(os.path.join(SITE, 'data_v4', 'units_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"units {len(feats):,} · big(≥{BIG_M2:,}㎡) {len(big)} · cross-sgg {sum(1 for f in feats if f['properties']['ns'] > 1)} · {tot/1024/1024:.1f} MB in {len(by_sgg)} files · units_big {os.path.getsize(os.path.join(SITE, 'data_v4', 'units_big.json.gz'))/1024:.0f} KB")
