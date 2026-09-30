# -*- coding: utf-8 -*-
"""대규모 후보 공간(50MW 이상)마다 가장 가까운 산업단지 — 후보지 찾기 화면의 강조 표시용.

GGI 검토의견(2026-10-01, 표 3-4 "각 대규모 클러스터별 시군의 거점 산단 하이라이트")을 사용자 결정대로
"가장 가까운 산업단지"로 구현한다. 새 거리를 만들지 않고, 정본 block_context 가 쓴 방법을 그대로 따라
"어느 산단이 그 최근접인지"만 밝힌다.

정본 방법(model/engine/block_context.py): 후보 공간 대표점(필지 대표점의 면적 가중 평균, EPSG:5186 x·y)
  ↔ damdan.gpkg 산업단지 경계, gpd.sjoin_nearest 거리 = dist_ind_m.
여기서: 같은 대표점(R2 block_context 의 x·y) ↔ damdan.gpkg(dan_id 중복 제거 — ind_bnd.json.gz 와 같은 순서)
  → 최근접 산단 이름·유형·거리·ind_bnd 피처 번호.
게이트: 다시 구한 거리가 발행값(units_big.json.gz 의 d, km 소수 둘째 자리)과 0.01 km 안에서 같아야 한다.
출력: data_v4/big_ind_near_v4.json — {generated, source, method, rows: {후보 공간 번호: {n, t, km, fi}}}
"""
import os, json, gzip, datetime
import duckdb
import geopandas as gpd

LR = r"C:\Users\user\새 폴더\Ledger_Rebuild"
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(SITE, 'data_v4', 'big_ind_near_v4.json')

big = json.load(gzip.open(os.path.join(SITE, 'data_v4', 'units_big.json.gz'), 'rt', encoding='utf-8'))
ids = [f['properties']['id'] for f in big['features']]
pub_d = {f['properties']['id']: f['properties'].get('d') for f in big['features']}
bc = duckdb.sql(f"SELECT lab, x, y FROM read_parquet('{os.path.join(LR, 'scenario_runs', 'R2_promo', 'block_context.parquet').replace(os.sep, '/')}') "
                f"WHERE lab IN ({','.join(map(str, ids))})").df()
assert len(bc) == len(ids), f'대표점 {len(bc)} ≠ 후보 {len(ids)}'
pts = gpd.GeoDataFrame(bc, geometry=gpd.points_from_xy(bc.x, bc.y), crs=5186)

dan = gpd.read_file(os.path.join(LR, 'sources', 'ind_complex', 'damdan.gpkg'))
dan = dan.drop_duplicates('dan_id').reset_index(drop=True).to_crs(5186)   # export_grid_v4 의 ind_bnd 와 같은 행·순서
dan['fi'] = dan.index
near = gpd.sjoin_nearest(pts, dan[['dan_name', 'cat_nam', 'fi', 'geometry']], how='left', distance_col='dist_m')
near = near.sort_values('dist_m').drop_duplicates('lab')                  # 같은 거리 동률이면 첫 행

rows, bad = {}, []
for _, r in near.iterrows():
    km = round(r.dist_m / 1000, 2)
    d = pub_d.get(int(r.lab))
    if d is None or abs(km - d) > 0.01:
        bad.append((int(r.lab), km, d))
    rows[str(int(r.lab))] = {'n': r.dan_name, 't': r.cat_nam, 'km': km, 'fi': int(r.fi)}
assert not bad, f'발행 거리와 다름: {bad}'

ib = json.load(gzip.open(os.path.join(SITE, 'data_v4', 'ind_bnd.json.gz'), 'rt', encoding='utf-8'))['features']
for k, v in rows.items():                                                   # 피처 번호 ↔ 이름 대조
    assert ib[v['fi']]['properties']['n'] == v['n'], (k, v, ib[v['fi']]['properties'])

out = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
       'source': 'scenario_runs/R2_promo/block_context.parquet (x·y) · sources/ind_complex/damdan.gpkg',
       'method': '정본 block_context 와 같은 대표점 ↔ 산업단지 경계 sjoin_nearest · 거리 = units_big d (게이트 0.01 km)',
       'rows': rows}
open(OUT, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
print('saved', OUT, len(rows), '곳 · 게이트 통과(거리 일치 · 이름 대조)')
