# -*- coding: utf-8 -*-
"""3D 레이어 스테이지 데이터 — 당진(44270) 판정 층위 5장 + 깔때기 수치.

층: L1 지목 전·답·과수원(우주) → L2 실경작 30% 이상 → L3 현행법 적격(앵커)
    → L4 등재 구획(ANCHOR) → L5 진흥지역 전체 개방 시 등재 구획(SOFT_A2)
지오메트리: 층별 dissolve → 간소화 60m(표시용) → 5186 평면 좌표(뷰박스 0-560×0-400 정규화)
수치: 정본 DB·scenario_runs 조회값 (표시 지오메트리와 무관하게 원본 기준)
산출: data_v4/stage_44270.json
사용: python pipeline/export/export_stage_v4.py"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np, pandas as pd, duckdb
import geopandas as gpd
import shapely

LR = os.path.join(ROOT, 'Ledger_Rebuild')
SGG = '44270'
W, H = 560, 400

con = duckdb.connect(os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb'), read_only=True)
# ADR-0039: 실경작 비율은 적격 조건이 아니다. 중간 층(L2)은 '물리·경사 통과'로 바꾼다
# (구판은 실경작 30% 층이었다 — 폐지된 조건을 판정 단계로 그리지 않는다).
flags = con.execute("""
  SELECT e.pnu,
         (e.L1_jimok AND e.L4_phys AND NOT COALESCE(e.excl_slope15,FALSE)
          AND NOT COALESCE(e.jimok_missing,FALSE)) live,
         (COALESCE(l.ownership,'') IN ('02','04','05','06')) pubcorp,
         (e.L1_jimok AND e.L3_s0 AND e.L4_phys
          AND NOT COALESCE(e.excl_slope15,FALSE) AND NOT COALESCE(e.jimok_missing,FALSE)
          AND NOT (l.class1_name LIKE '%개발제한구역%' OR l.class2_name LIKE '%개발제한구역%')
          AND l.class1_name NOT IN ('보전관리지역','보전녹지지역')
          AND COALESCE(l.class2_name,'') NOT IN ('보전관리지역','보전녹지지역')) anchor
  FROM elig_v2 e JOIN ledger l USING(pnu)
  WHERE e.sgg = ? AND l.category IN ('01','02','03')""", [SGG]).fetch_df()
con.close()
print(f"당진 전답과 우주 {len(flags):,} · 물리·경사 통과 {int(flags['live'].sum()):,} · "
      f"앵커 {int(flags['anchor'].sum()):,}", flush=True)

g = gpd.read_file(os.path.join(ROOT, 'Cadastre_All', f'{SGG}.gpkg')).to_crs(5186)
g = g.drop_duplicates('pnu').set_index('pnu')

MIN_PART = 80_000.0     # 표시 최소 조각 8ha — 그 미만 섬·구멍은 장식 지도에서 생략

def blob(pnus, tol=120.0):
    """층 표시용 뭉침: 도로·하천으로 잘게 쪼개진 필지 union을 closing buffer(±100m)로
    '지대'로 뭉친 뒤 간소화 — 8ha 필터가 실제 분포를 지우지 않게 한다 (표시 전용)."""
    sub = g.reindex(pnus)
    geo = sub.geometry[sub.geometry.notna()].values
    u = shapely.union_all(geo)
    u = shapely.buffer(shapely.buffer(u, 100.0), -100.0)
    u = shapely.simplify(u, tol)
    geos = u.geoms if u.geom_type == 'MultiPolygon' else [u]
    keep = []
    for p in geos:
        if p.area < MIN_PART:
            continue
        holes = [h for h in p.interiors if shapely.Polygon(h).area >= MIN_PART]
        keep.append(shapely.Polygon(p.exterior, holes))
    return shapely.MultiPolygon(keep) if keep else u

L1 = blob(flags['pnu'].values)
L2 = blob(flags.loc[flags['live'], 'pnu'].values)
_anc = flags['anchor'].fillna(False).astype(bool)
L3 = blob(flags.loc[_anc, 'pnu'].values)
# ADR-0040: 소유 우주(법인·국공유)가 이제 가장 큰 좁힘이다 — 등재 문턱(θ)은 폐지됐으므로
# 그 자리에 이 층을 둔다. 마지막 층은 진흥지역 전체 개방 시의 정본 연접 구획.
_pub = _anc & flags['pubcorp'].fillna(False).astype(bool)
L4 = blob(flags.loc[_pub, 'pnu'].values)
m5 = pd.read_parquet(os.path.join(LR, 'scenario_runs', 'R3_zone_all', 'members.parquet'))
L5 = blob(m5.loc[m5['pnu'].str[:5] == SGG, 'pnu'].values, 80.0)

# 뷰박스 정규화 (여백 4%)
x0, y0, x1, y1 = shapely.bounds(L1)
pad = 0.04 * max(x1 - x0, y1 - y0)
x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
sc = min(W / (x1 - x0), H / (y1 - y0))
ox = (W - (x1 - x0) * sc) / 2
oy = (H - (y1 - y0) * sc) / 2

def paths(u):
    out = []
    geos = u.geoms if u.geom_type == 'MultiPolygon' else [u]
    for p in geos:
        for ring in [p.exterior] + list(p.interiors):
            xs, ys = np.asarray(ring.coords).T
            px = (xs - x0) * sc + ox
            py = H - ((ys - y0) * sc + oy)
            out.append('M' + ' '.join(f'{a:.1f},{b:.1f}' for a, b in zip(px, py)) + 'Z')
    return ' '.join(out)

# 깔때기 수치 — 정본 조회값 (구획 값은 시군 구간 필지 수·색인 면적)
idx = json.load(open(os.path.join(SITE, 'data_v4', 'clusters_index.json'), encoding='utf-8'))
ANC = idx['sgg'][SGG]['R0_current']; A2 = idx['sgg'][SGG]['R3_zone_all']
out = {
    'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    'sgg': SGG, 'name': '충남 당진시', 'w': W, 'h': H,
    'layers': [
        {'k': 'L1', 't': '지목 전·답·과수원', 'd': f"{len(flags):,}필지 — 분석 우주",
         'path': paths(L1)},
        {'k': 'L2', 't': '물리·경사 통과', 'd': f"{int(flags['live'].sum()):,}필지 — 건물·수역·산단 없음, 경사 15° 이하",
         'path': paths(L2)},
        {'k': 'L3', 't': '진흥✕·보호✕ 적격', 'd': f"{int(flags['anchor'].fillna(False).sum()):,}필지 — 구조·경사·용도 3종 통과, 농업진흥지역 밖",
         'path': paths(L3)},
        {'k': 'L4', 't': '연접 구획 ≥66,667㎡ (현행)', 'd': f"{ANC['k']:,}구획 · {ANC['km2']:,}km² — 66,667㎡는 3MW 등가의 읽기 눈금(문턱 아님)",
         'path': paths(L4)},
        {'k': 'L5', 't': '진흥지역 전체 개방 시', 'd': f"{A2['k']:,}구획 · {A2['km2']:,}km² — 수단 B 상한",
         'path': paths(L5)},
    ],
}
fp = os.path.join(SITE, 'data_v4', 'stage_44270.json')
json.dump(out, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f"stage_44270.json: {os.path.getsize(fp)/1e3:.0f} KB")
