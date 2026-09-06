# -*- coding: utf-8 -*-
"""신·구 읍면동 코드 다리 — {신 경계 emd8 → 구 계통 emd8}.

계통 자산(KEPCO, 2026-07 수집)은 구 행정코드, 경계(V-World LT_C_ADEMD_INFO,
2026-08 수집)는 2026 개편 신 코드(광주·전남 통합 '12', 인천·화성 구 신설 등).
export_grid_v4.py 의 검증된 로직을 모듈로 뗀 것 — ① bjd_code 이름 대조(말소
remainder = 현행 remainder) ② 잔여는 필지 대표점 공간 매칭(구 emd 필지 → 신 경계).
grid_v4 쪽 원본 인라인은 다음 재실행 때 이 모듈로 통일 예정(중복 기록: PR-0029).
"""
import os


def build_alias(con, bnd_gdf, old_codes):
    """con: duckdb(read) · bnd_gdf: 경계 GeoDataFrame(emd_cd 보유) · old_codes: 구 emd8 집합.
    반환 {신 emd8: 구 emd8} — 경계에 이미 있는 구 코드는 매핑 불필요라 제외."""
    import geopandas as gpd
    bnd_codes = set(str(x)[:8] for x in bnd_gdf['emd_cd'])
    old_missing = sorted(set(old_codes) - bnd_codes)
    alias = {}
    if not old_missing:
        return alias
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
    rest = [o for o in old_missing if o not in mapped]
    if rest:
        from paths import ROOT
        CAD = os.path.join(ROOT, 'Cadastre_All')
        g5186 = bnd_gdf.set_index(bnd_gdf['emd_cd'].astype(str).str[:8]).to_crs(5186)
        by_sgg = {}
        for o in rest:
            by_sgg.setdefault(o[:5], []).append(o)
        for sgg, olds in sorted(by_sgg.items()):
            fp = os.path.join(CAD, f'{sgg}.gpkg')
            if not os.path.exists(fp):
                continue
            pc = gpd.read_file(fp, columns=['pnu']).to_crs(5186)
            pc['e8'] = pc['pnu'].str[:8]
            pts = pc[pc['e8'].isin(olds)].groupby('e8').head(3).copy()
            pts['geometry'] = pts.geometry.representative_point()
            j = gpd.sjoin(pts, g5186[['geometry']], how='inner', predicate='within')
            rc = 'index_right' if 'index_right' in j.columns else g5186.index.name
            for e8, new in j.groupby('e8')[rc].agg(lambda s: s.mode().iat[0]).items():
                if str(new)[:8] not in alias:
                    alias[str(new)[:8]] = e8
    return alias
