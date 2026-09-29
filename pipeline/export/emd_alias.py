# -*- coding: utf-8 -*-
"""신·구 읍면동 코드 다리 — {신 경계 emd8 → 구 계통 emd8}.

계통 자산(KEPCO 스냅숏)은 구 행정코드, 경계(V-World LT_C_ADEMD_INFO, 2026-08 수집)는 2026 개편 신 코드
(광주·전남 통합 '전남광주통합특별시', 인천·화성 구 신설 등). 두 단계로 잇는다:
  ① 이름 대조 — bjd_code(폐지 포함)의 **행정계층 이름**(시도 · 시군구 · 읍면동)을 그대로 비교한다.
  ② 잔여는 필지 대표점 공간 매칭(구 읍면동 필지 → 신 경계 폴리곤).

2026-09-24 정정 (감사 F-26 · NEW-F-03)
  전에는 ①의 키가 '시도 이름을 뗀 나머지'(시군구+읍면동)였다. 그래서 인천 중구의 구 코드 7개가 부산·대전·대구 중구의
  같은 이름 동에 붙었고(그 동들은 자기 계통 값이 있어 다리가 쓰이지 않았다), 이미 '연결됨'으로 처리되어 ②로도 넘어가지
  못해 값 7건이 지도에서 사라졌다. 이제 규칙은:
    · 시도가 같을 때만 잇는다 — 시군구·읍면동 이름이 같아도 다른 시도면 잇지 않는다.
    · 시도가 바뀌는 경우는 bjd_code 가 **시도 행 자체를 폐지로 싣고 있는** 통합(광주광역시·전라남도 → 전남광주통합특별시)만.
      이 쌍은 SIDO_MERGE 로 명시하고, bjd_code 의 시도 행 폐지 상태가 이 목록과 다르면 멈춘다(새 개편은 사람이 확인).
    · 후보가 둘 이상이면 AMBIGUOUS — 잇지 않는다(②로 넘긴다). 부분 문자열·코드 산술·첫 일치 선택 없음.
    · ②에서 신 코드 하나에 구 코드 둘 이상이 모이면 AMBIGUOUS — 어느 값도 고르지 않는다.
"""
import os

# bjd_code(code.go.kr 법정동코드 전체자료)의 시도 행: 광주광역시·전라남도 = 폐지, 전남광주통합특별시 = 현행.
SIDO_MERGE = {'광주광역시': '전남광주통합특별시', '전라남도': '전남광주통합특별시'}


def sido_rows(con):
    """[(시도 이름, alive)] — 코드 10자리 중 시도 행(뒤 8자리 0)."""
    return con.execute("SELECT name_full, alive FROM bjd_code WHERE SUBSTR(code10,3,8)='00000000'").fetchall()


def check_sido_merge(srows, used_sidos):
    """다리에 실제로 쓰이는 구 코드의 시도가 폐지 시도라면 SIDO_MERGE 에 적힌 것이어야 한다.
    (bjd_code 에는 직할시·강원도 등 과거 폐지 시도 이름도 있다 — 쓰이지 않는 것은 묻지 않는다.)"""
    alive = {n for n, a in srows if a}
    dead = {n for n, a in srows if not a} - alive
    bad = sorted(sd for sd in used_sidos if sd in dead and sd not in SIDO_MERGE)
    if bad or not set(SIDO_MERGE.values()) <= alive or not set(SIDO_MERGE) <= dead:
        raise SystemExit(f"[FAIL] 폐지 시도의 구 코드가 SIDO_MERGE 밖에 있다 {bad} (또는 통합 쌍의 폐지·현행 상태가 기록과 다름). "
                         "새 행정 개편은 사람이 확인한 뒤 SIDO_MERGE 에 적는다(추정 연결 금지).")


def name_alias(rows, old_missing, bnd_codes):
    """① 이름 대조. rows = [(emd8, name_full, alive)] (리 제외 읍면동 행).
    반환 (alias {신 emd8: 구 emd8}, report{linked, ambiguous, cross_sido_rejected, no_name})."""
    alive_by = {}                     # (시도, 시군구+읍면동) → [emd8]
    dead_name = {}                    # 구 emd8 → (시도, 나머지)
    for e8, nm, al in rows:
        parts = nm.split()
        key = (parts[0], ' '.join(parts[1:]))
        if al:
            alive_by.setdefault(key, []).append(e8)
        else:
            dead_name[e8] = key
    rest_by = {}                      # 나머지 이름 → 시도들(교차 시도 거부 보고용)
    for (sd, rest), es in alive_by.items():
        rest_by.setdefault(rest, set()).add(sd)
    alias, rep = {}, {'linked': [], 'ambiguous': [], 'cross_sido_rejected': [], 'no_name': []}
    taken = {}
    for old in sorted(old_missing):
        if old not in dead_name:
            rep['no_name'].append(old)
            continue
        sd, rest = dead_name[old]
        tgt_sd = SIDO_MERGE.get(sd, sd)
        cand = [c for c in alive_by.get((tgt_sd, rest), []) if c in bnd_codes]
        others = sorted(rest_by.get(rest, set()) - {tgt_sd})
        if len(cand) == 1:
            taken.setdefault(cand[0], []).append(old)
        elif len(cand) > 1:
            rep['ambiguous'].append((old, sorted(cand)))
        elif others:
            rep['cross_sido_rejected'].append((old, sd + ' ' + rest, others))
    for new, olds in sorted(taken.items()):
        if len(olds) == 1:
            alias[new] = olds[0]
            rep['linked'].append((olds[0], new))
        else:                          # 다대일 — 어느 값도 고르지 않는다
            rep['ambiguous'].extend((o, [new]) for o in olds)
    return alias, rep


def spatial_alias(rest, bnd_gdf, cad_dir, taken_new=frozenset()):
    """② 공간 매칭 — 구 읍면동 필지 대표점(최대 3점) → 신 경계 최빈 폴리곤.
    반환 (alias, report{linked, many_to_one, unmatched, taken_conflict})."""
    import geopandas as gpd
    g5186 = bnd_gdf.set_index(bnd_gdf['emd_cd'].astype(str).str[:8]).to_crs(5186)
    by_sgg = {}
    for o in rest:
        by_sgg.setdefault(o[:5], []).append(o)       # 필지 파일이 시군 단위라서 묶을 뿐 — 코드를 변환하지 않는다
    hits = {}
    for sgg, olds in sorted(by_sgg.items()):
        fp = os.path.join(cad_dir, f'{sgg}.gpkg')
        if not os.path.exists(fp):
            continue
        pc = gpd.read_file(fp, columns=['pnu']).to_crs(5186)
        pc['e8'] = pc['pnu'].str[:8]
        pts = pc[pc['e8'].isin(olds)].groupby('e8').head(3).copy()
        pts['geometry'] = pts.geometry.representative_point()
        j = gpd.sjoin(pts, g5186[['geometry']], how='inner', predicate='within')
        rc = 'index_right' if 'index_right' in j.columns else g5186.index.name
        for e8, new in j.groupby('e8')[rc].agg(lambda s: s.mode().iat[0]).items():
            hits.setdefault(str(new)[:8], []).append(e8)
    alias, rep = {}, {'linked': [], 'many_to_one': [], 'taken_conflict': [], 'unmatched': []}
    for new, olds in sorted(hits.items()):
        if new in taken_new:
            rep['taken_conflict'].extend(olds)
        elif len(olds) > 1:
            rep['many_to_one'].append((new, sorted(olds)))
        else:
            alias[new] = olds[0]
            rep['linked'].append((olds[0], new))
    got = {o for v in hits.values() for o in v}
    rep['unmatched'] = sorted(set(rest) - got)
    return alias, rep


def build_alias(con, bnd_gdf, old_codes, with_report=False):
    """con: duckdb(read) · bnd_gdf: 경계 GeoDataFrame(emd_cd 보유) · old_codes: 구 emd8 집합.
    반환 {신 emd8: 구 emd8} — 경계에 이미 있는 구 코드는 매핑 불필요라 제외."""
    bnd_codes = set(str(x)[:8] for x in bnd_gdf['emd_cd'])
    old_missing = sorted(set(old_codes) - bnd_codes)
    if not old_missing:
        return ({}, {}) if with_report else {}
    rows = con.execute("""SELECT emd8, name_full, alive FROM bjd_code
                          WHERE NOT is_ri AND LENGTH(emd8)=8 AND SUBSTR(emd8,6,3)<>'000'""").fetchall()
    _nm = {e: n for e, n, _ in rows}
    check_sido_merge(sido_rows(con), {_nm[o].split()[0] for o in old_missing if o in _nm})
    alias, r1 = name_alias(rows, old_missing, bnd_codes)
    rest = [o for o in old_missing if o not in set(alias.values())]
    r2 = {}
    if rest:
        from paths import ROOT
        a2, r2 = spatial_alias(rest, bnd_gdf, os.path.join(ROOT, 'Cadastre_All'), taken_new=frozenset(alias))
        alias.update(a2)
    return (alias, {'name': r1, 'spatial': r2}) if with_report else alias
