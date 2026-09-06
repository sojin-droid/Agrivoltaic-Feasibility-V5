# -*- coding: utf-8 -*-
"""계통·산업단지 탭 데이터 export — data_v4/grid_emd.json.gz · ind_bnd.json.gz · grid_summary.json.

원천(전량 기존 정본 자산):
  · grid_emd_v3 (DB) — KEPCO 분산전원 연계정보 재구축 v3, 전국 5,066 읍면동
    (vol3 = 배전선로 잔여 연계가능용량, 설비별 불일치는 최솟값으로 보수 확정,
     equal = 걸친 읍면동 균등배분 / shared = 공유 미조정 상한)
  · sources/emd_bnd/emd_bnd.gpkg — V-World LT_C_ADEMD 읍면동 경계 (표기용, v5_04)
  · sources/ind_complex/damdan.gpkg — V-World LT_C_DAMDAN 산업단지 경계 1,363개 (v5_03)
게이트: grid_emd_v3 행수·status 분포를 출력하고, 조인 실패(경계 없음/값 없음)를 병기(숨은 배제 금지).
사용: python pipeline/export/export_grid_v4.py
"""
import os, sys, json, gzip, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import geopandas as gpd
import pandas as pd
import shapely
sys.path.insert(0, MODEL)
import query as Q

LR = os.path.join(ROOT, 'Ledger_Rebuild')
GEN = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
SIMPLIFY_EMD = 150.0    # m — 전국 채색 표시용
SIMPLIFY_IND = 40.0


def rnd(cc, nd=4):
    if isinstance(cc[0], (list, tuple)):
        return [rnd(x, nd) for x in cc]
    return [round(cc[0], nd), round(cc[1], nd)]


def gz(fo, obj):
    raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    with gzip.open(fo + '.tmp', 'wb', compresslevel=9) as z:
        z.write(raw)
    os.replace(fo + '.tmp', fo)
    print(f"{os.path.basename(fo)}: {os.path.getsize(fo)/1e6:,.1f} MB")


con = Q.db()
grid = {r[0]: r for r in con.execute("""
  SELECT emd8, status, ROUND(vol3_equal_mw,1), ROUND(vol3_shared_mw,1) FROM grid_emd_v3""").fetchall()}
names = dict(con.execute("SELECT emd8, emd_name FROM kepco_dong_v3").fetchall())
ind_cnt = dict(con.execute("SELECT cat_nam, COUNT(1) FROM ind_complex_bnd GROUP BY 1").fetchall())
print(f"grid_emd_v3 {len(grid):,}행 · ok {sum(1 for v in grid.values() if v[1]=='ok'):,}")

# ── 신·구 행정코드 대조 (각주 17 선례) ──
# 계통(수집 2026-07)은 구 코드, 경계(LT_C_ADEMD_INFO)는 2026 신 코드(광주·전남 통합 '12',
# 인천·화성 구 신설). ① bjd_code 이름 대조(말소 remainder = 현행 remainder) ② 잔여는
# 필지 대표점 공간 매칭(구 emd 필지 1점 → 신 경계 폴리곤).
g = gpd.read_file(os.path.join(LR, 'sources', 'emd_bnd', 'emd_bnd.gpkg'))
bnd_codes = set(str(x)[:8] for x in g['emd_cd'])
old_missing = sorted(set(grid) - bnd_codes)
alias = {}                                      # 신 경계 코드 → 구 계통 코드
if old_missing:
    rows = con.execute("""SELECT emd8, name_full, alive FROM bjd_code
                          WHERE NOT is_ri AND LENGTH(emd8)=8 AND SUBSTR(emd8,6,3)<>'000'""").fetchall()
    rem_alive, rem_dead = {}, {}
    for e8, nm, alive in rows:
        rem = ' '.join(nm.split()[1:])          # 시도 접두어 제거
        (rem_alive if alive else rem_dead).setdefault(rem, []).append(e8)
    for old in list(old_missing):
        nm = next((r for r, es in rem_dead.items() if old in es), None)
        cand = rem_alive.get(nm, [])
        if nm and len(cand) == 1 and cand[0] in bnd_codes:
            alias[cand[0]] = old
    mapped = set(alias.values())
    print(f"이름 대조 매핑 {len(alias):,} / 잔여 {len(old_missing)-len(mapped):,}")
    rest = [o for o in old_missing if o not in mapped]
    if rest:
        import glob as _g
        CAD = os.path.join(ROOT, 'Cadastre_All')
        gb = g.set_index(g['emd_cd'].astype(str).str[:8])
        g5186 = gb.to_crs(5186)
        by_sgg = {}
        for o in rest:
            by_sgg.setdefault(o[:5], []).append(o)
        for sgg, olds in sorted(by_sgg.items()):
            fp = os.path.join(CAD, f'{sgg}.gpkg')
            if not os.path.exists(fp):
                continue
            pc = gpd.read_file(fp, columns=['pnu'], rows=None).to_crs(5186)
            pc['e8'] = pc['pnu'].str[:8]
            pts = pc[pc['e8'].isin(olds)].groupby('e8').head(3).copy()
            pts['geometry'] = pts.geometry.representative_point()
            j = gpd.sjoin(pts, g5186[['geometry']], how='inner', predicate='within')
            rc = 'index_right' if 'index_right' in j.columns else g5186.index.name
            for e8, new in j.groupby('e8')[rc].agg(lambda s: s.mode().iat[0]).items():
                if str(new)[:8] not in alias:
                    alias[str(new)[:8]] = e8
        print(f"공간 매칭 후 총 매핑 {len(alias):,}")

# ── 읍면동 choropleth ──
g = g.to_crs(5186)
g['geometry'] = g.geometry.simplify(SIMPLIFY_EMD)
g = g.to_crs(4326)
feats, no_grid, no_bnd = [], 0, set(grid)
for _, r in g.iterrows():
    c = str(r['emd_cd'])[:8]
    key = c if c in grid else alias.get(c)
    v = grid.get(key) if key else None
    if key:
        no_bnd.discard(key)
    if v is None:
        st, lo, hi = 'nodata', None, None
        no_grid += 1
    else:
        st, lo, hi = v[1], v[2], v[3]
    geo = shapely.geometry.mapping(r.geometry)
    feats.append({'type': 'Feature',
                  'geometry': {'type': geo['type'], 'coordinates': rnd(list(geo['coordinates']))},
                  'properties': {'c': c, 'n': r['emd_nm'] or names.get(key or c, c),
                                 's': st, 'lo': lo, 'hi': hi}})
con.close()
gz(os.path.join(OUT, 'grid_emd.json.gz'),
   {'type': 'FeatureCollection', 'generated': GEN, 'features': feats})
print(f"읍면동 {len(feats):,} — 계통값 없음(경계만) {no_grid:,} · 경계 없음(계통만) {len(no_bnd):,}")

# ── 산업단지 경계 ──
d = gpd.read_file(os.path.join(LR, 'sources', 'ind_complex', 'damdan.gpkg'))
d = d.drop_duplicates('dan_id')          # 수집 중복 제거 — DB ind_complex_bnd(1,363)와 일치
d = d.to_crs(5186)
d['geometry'] = d.geometry.simplify(SIMPLIFY_IND)
d = d.to_crs(4326)
ifeats = []
for _, r in d.iterrows():
    geo = shapely.geometry.mapping(r.geometry)
    ifeats.append({'type': 'Feature',
                   'geometry': {'type': geo['type'], 'coordinates': rnd(list(geo['coordinates']))},
                   'properties': {'n': r['dan_name'], 't': r['cat_nam']}})
gz(os.path.join(OUT, 'ind_bnd.json.gz'),
   {'type': 'FeatureCollection', 'generated': GEN, 'features': ifeats})

# ── 요약 ──
ok = [v for v in grid.values() if v[1] == 'ok']
summary = {
    'generated': GEN,
    'emd_total': len(grid),
    'emd_ok': len(ok),
    'emd_unknown': len(grid) - len(ok),
    'bnd_only': no_grid,
    'lo_sum_mw': round(sum(v[2] or 0 for v in ok)),
    'hi_sum_mw': round(sum(v[3] or 0 for v in ok)),
    'ind_total': int(sum(ind_cnt.values())),
    'ind_by_cat': {k: int(v) for k, v in sorted(ind_cnt.items(), key=lambda x: -x[1])},
}
json.dump(summary, open(os.path.join(OUT, 'grid_summary.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('grid_summary:', summary)
