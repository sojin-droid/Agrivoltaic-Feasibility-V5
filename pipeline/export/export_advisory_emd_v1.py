# -*- coding: utf-8 -*-
"""자문 화면용 읍면동 경계 — 경기도(+인접 약 5 km) · 인접 경계 공유 유지 단순화.

왜: grid_emd.json.gz 의 읍면동 폴리곤은 전국 계통 채색용으로 150 m 허용오차로 도형마다 따로 단순화돼,
확대하면 이웃 경계가 겹치거나 벌어져 이중 점선·농지를 가로지르는 선으로 보인다(수원 비행장 부근 인접 쌍
겹침 최대 13 %). 자문자가 "행정경계 자료"의 신뢰성을 이 표시 오차로 판단하지 않도록, 같은 원천에서
경계 공유를 유지하는 coverage 단순화(8 m)로 표시용 경계를 따로 만든다.

원천: Ledger_Rebuild/sources/emd_bnd/emd_bnd.gpkg (V-World LT_C_ADEMD 읍면동 경계, 2026-08-27 수집) — 값·코드 무변경.
처리: 경기도 경계 상자 ±0.05° 안의 읍면동 → make_valid(폴리곤 부분만) → EPSG:5186 → shapely.coverage_simplify(8 m) → EPSG:4326 · 좌표 1e-5°.
출력: data_v4/advisory/gg_emd_bnd_v1.json.gz — {generated, source, method, scope, features:[{c, n, geometry}]}
후보 공간·판정·계통 값과 무관한 표시 전용 자산이다.
"""
import os, json, gzip, datetime
import geopandas as gpd
import shapely
from shapely.geometry import box

SRC = r"C:\Users\user\새 폴더\Ledger_Rebuild\sources\emd_bnd\emd_bnd.gpkg"
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(SITE, 'data_v4', 'advisory', 'gg_emd_bnd_v1.json.gz')
TOL_M = 8.0

g = gpd.read_file(SRC)
b = g[g.emd_cd.str[:2] == '41'].total_bounds
sub = g[g.intersects(box(b[0] - 0.05, b[1] - 0.05, b[2] + 0.05, b[3] + 0.05))].copy()


def polygonal(x):
    x = shapely.make_valid(x)
    parts = [q for q in (x.geoms if hasattr(x, 'geoms') else [x]) if q.geom_type in ('Polygon', 'MultiPolygon') and not q.is_empty]
    return shapely.union_all(parts) if parts else x


p = gpd.GeoSeries([polygonal(x) for x in sub.to_crs(5186).geometry], crs=5186)
assert p.is_valid.all(), '유효하지 않은 도형이 남음'
s = gpd.GeoSeries(shapely.coverage_simplify(p.values, TOL_M), crs=5186).to_crs(4326)
feats = [{'type': 'Feature', 'properties': {'c': c, 'n': n},
          'geometry': json.loads(shapely.to_geojson(shapely.set_precision(x, 1e-5)))}
         for c, n, x in zip(sub.emd_cd, sub.emd_nm, s)]
out = {'type': 'FeatureCollection', 'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
       'source': 'sources/emd_bnd/emd_bnd.gpkg — V-World LT_C_ADEMD 읍면동 경계 (2026-08-27 수집)',
       'method': f'make_valid → EPSG:5186 coverage_simplify {TOL_M:g} m (인접 경계 공유 유지) → EPSG:4326 · 좌표 1e-5°',
       'scope': f'경기도 경계 상자 ±0.05° 안 읍면동 {len(feats)}개 (경기 {int((sub.emd_cd.str[:2] == "41").sum())})',
       'features': feats}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with gzip.open(OUT, 'wt', encoding='utf-8', compresslevel=9) as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print('saved', OUT, os.path.getsize(OUT), 'bytes ·', out['scope'])
