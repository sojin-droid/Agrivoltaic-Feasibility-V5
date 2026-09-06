# -*- coding: utf-8 -*-
"""02_derive_attrs.py — 필지 파생속성 산출 (Phase 1 확정 필터 체계)
=================================================================
입력: pipeline_out/parcels_clean/{sgg}.parquet + Base gpkg(폴리곤)
      D_Regulation.gpkg / phase1_audit/new_layers.gpkg(상수원)
      phase1_audit/military_tags.sqlite (파주·김포 군사구역)
      GIS_DATA/farm_map_shp/*.gpkg (시설재배) / GIS_DATA/korea_slope.gpkg
      complex_integrated.csv (산단 좌표)
출력: pipeline_out/parcels_final/{sgg}.parquet

사용: python 02_derive_attrs.py [sgg코드들 콤마구분 | all | all_nonmil]
"""
import os, sys, io, sqlite3, time, gc
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
from shapely.ops import unary_union

BASE = r"C:\Users\user\새 폴더"
CADASTRE = os.path.join(BASE, "Base", "Base")
OUT_ROOT = os.path.join(BASE, "pipeline_out")
CLEAN_DIR = os.path.join(OUT_ROOT, "parcels_clean")
FINAL_DIR = os.path.join(OUT_ROOT, "parcels_final")
D_GPKG = os.path.join(BASE, "D_Regulation.gpkg")
NEW_GPKG = os.path.join(BASE, "phase1_audit", "new_layers.gpkg")
MIL_DB = os.path.join(BASE, "phase1_audit", "military_tags.sqlite")
GIS = os.path.join(BASE, "GIS_DATA")
os.makedirs(FINAL_DIR, exist_ok=True)

# 주의: 44180=보령, 44210=서산 (구 라벨 오류 정정 — council_name 검증 2026-07-13)
#       44131=천안동남, 44133=천안서북 (행정표준코드·좌표 검증 2026-07-13 — 구 라벨 스왑 정정)
SGG = {
    "44270": ("당진", "FARM_CHUNGNAM.gpkg"), "44180": ("보령", "FARM_CHUNGNAM.gpkg"),
    "44200": ("아산", "FARM_CHUNGNAM.gpkg"), "44131": ("천안동남", "FARM_CHUNGNAM.gpkg"),
    "44133": ("천안서북", "FARM_CHUNGNAM.gpkg"), "44210": ("서산", "FARM_CHUNGNAM.gpkg"),
    "44800": ("홍성", "FARM_CHUNGNAM.gpkg"), "41590": ("화성", "FARM_GYEONGGI.gpkg"),
    "41220": ("평택", "FARM_GYEONGGI.gpkg"), "41463": ("용인", "FARM_GYEONGGI.gpkg"),
    "41271": ("안산", "FARM_GYEONGGI.gpkg"), "41390": ("시흥", "FARM_GYEONGGI.gpkg"),
    "41500": ("이천", "FARM_GYEONGGI.gpkg"), "41480": ("파주", "FARM_GYEONGGI.gpkg"),
    "41570": ("김포", "FARM_GYEONGGI.gpkg"),
    # 2026-07-14 확장 (A안) — 팜맵은 FARM_MERGED_FINAL에서 재추출한 FARM_NEW 사용
    "44810": ("예산", "FARM_NEW.gpkg"), "41461": ("용인처인", "FARM_NEW.gpkg"),
    "41465": ("용인수지", "FARM_NEW.gpkg"), "41273": ("안산단원", "FARM_NEW.gpkg"),
    # 2026-07-15 Phase E1 (B 지역 11개 코드) — geometry=팜맵(15_build_b_regions)
    "28200": ("인천남동", "FARM_B.gpkg"), "46230": ("광양", "FARM_B.gpkg"),
    "46130": ("여수", "FARM_B.gpkg"), "47111": ("포항남", "FARM_B.gpkg"),
    "47113": ("포항북", "FARM_B.gpkg"), "47190": ("구미", "FARM_B.gpkg"),
    "31110": ("울산중", "FARM_B.gpkg"), "31140": ("울산남", "FARM_B.gpkg"),
    "31170": ("울산동", "FARM_B.gpkg"), "31200": ("울산북", "FARM_B.gpkg"),
    "31710": ("울주", "FARM_B.gpkg"),
}
MIL_SGG = {"41480", "41570"}

# 실명 제외 그룹 ← D_Regulation 레이어 (Phase 1 §7.2 확정)
EXCL_GROUPS = {
    "excl_heritage":    ["LT_C_UO301_fixed"],
    "excl_wildlife":    ["LT_C_UM221_fixed"],
    "excl_natpark":     ["LT_C_WGISNPGUG_fixed", "LT_C_WGISNPDO_fixed",
                         "LT_C_WGISNPGUN"],
    "excl_baekdu":      ["LT_C_UF901_fixed"],
    "excl_greenbuf":    ["LT_C_UQ162_fixed"],
    "excl_village":     ["LT_C_UQ128_fixed"],
    "excl_slope15":     ["slope_over_15"],
    "excl_nature_zone": ["LT_C_UQ114_fixed"],   # S0만 제외
}
COMMON_EXCL = ["excl_heritage", "excl_wildlife", "excl_natpark", "excl_baekdu",
               "excl_greenbuf", "excl_village", "excl_slope15", "excl_water",
               "excl_mil_control", "excl_tech"]

OWN_MAP = {"개인": "개인", "국유지": "국유", "시/도유지": "공공", "군유지": "공공",
           "법인": "법인", "종중": "종중·종교", "종교단체": "종중·종교",
           "외국인/외국공공기관": "기타", "기타단체": "기타", "지방자치단체": "공공"}

NB_RADIUS_M = 500.0


def process(sgg):
    name, farm_fn = SGG[sgg]
    t0 = time.time()
    df = pd.read_parquet(os.path.join(CLEAN_DIR, f"{sgg}.parquet"))
    df["pnu"] = df["pnu"].astype(str).str.zfill(19)

    # ── 보충본 병합 (지목 결측 복구 + 좌표 교정, 07_build_supplement 산출) ──
    SUPP = os.path.join(OUT_ROOT, "nojimok_repair", "supplement")
    sp = os.path.join(SUPP, f"{sgg}.parquet")
    if os.path.exists(sp):
        sup = pd.read_parquet(sp)
        sup["pnu"] = sup["pnu"].astype(str).str.zfill(19)
        df = pd.concat([df[~df["pnu"].isin(set(sup["pnu"]))], sup], ignore_index=True)
        print(f"  보충본 병합 {len(sup):,}건")
    dropf = os.path.join(SUPP, "drop_pnu.csv")
    if os.path.exists(dropf):
        dl = set(pd.read_csv(dropf, dtype=str)["pnu"].str.zfill(19))
        if dl:
            df = df[~df["pnu"].isin(dl)]
    df["sgg_name"] = name  # 라벨 일원화 (천안 스왑 정정 포함)

    # ── 폴리곤 로드 (정제 통과 pnu만) ──
    g = gpd.read_file(os.path.join(CADASTRE, f"{sgg}.gpkg"))
    pnu_col = next(c for c in g.columns if c.lower() == "pnu")
    g = g.rename(columns={pnu_col: "pnu"})[["pnu", "geometry"]]
    g["pnu"] = g["pnu"].astype(str).str.zfill(19)
    g = g[g["pnu"].isin(set(df["pnu"]))].drop_duplicates("pnu")
    bad = ~g.geometry.is_valid
    if bad.any():
        g.loc[bad, "geometry"] = g.loc[bad, "geometry"].buffer(0)
    g = g.to_crs(epsg=5186)
    # 보충 폴리곤 (복구 농지 신규 + 좌표 오류 교정분은 Base 대신 교체)
    sgp = os.path.join(SUPP, f"{sgg}_geom.gpkg")
    if os.path.exists(sgp):
        g2 = gpd.read_file(sgp)[["pnu", "geometry"]]
        g2["pnu"] = g2["pnu"].astype(str).str.zfill(19)
        g2 = g2[g2["pnu"].isin(set(df["pnu"]))].to_crs(epsg=5186)
        g = pd.concat([g[~g["pnu"].isin(set(g2["pnu"]))], g2], ignore_index=True)
    print(f"[{name}] 필지 {len(df):,} / 폴리곤 {len(g):,} ({time.time()-t0:.0f}s)")

    # ── D_Regulation + 상수원 레이어 태깅 ──
    minx, miny, maxx, maxy = g.total_bounds
    d = gpd.read_file(D_GPKG, bbox=(minx, miny, maxx, maxy))
    um = gpd.read_file(NEW_GPKG, layer="LT_C_UM710").to_crs(epsg=5186)
    # 신규 확장 지역 상수원 (11_assemble 산출 — 원본 new_layers는 15개 시군 bbox 한정)
    for _umf in ("um710_new.gpkg", "um710_b.gpkg"):
        um_new = os.path.join(OUT_ROOT, "new_regions", _umf)
        if os.path.exists(um_new):
            um = pd.concat([um, gpd.read_file(um_new).to_crs(epsg=5186)], ignore_index=True)
    um = um.cx[minx:maxx, miny:maxy]

    hit_geoms = {}   # pnu -> [geometry, ...] (중첩비율용)
    for grp, codes in EXCL_GROUPS.items():
        sub = d[d["layer"].isin(codes)]
        df[grp] = 0
        if len(sub):
            sj = gpd.sjoin(g, sub[["geometry"]].reset_index(drop=True),
                           how="inner", predicate="intersects")
            hits = set(sj["pnu"])
            df[grp] = df["pnu"].isin(hits).astype(int)
            if grp != "excl_nature_zone":
                for pnu, ridx in zip(sj["pnu"], sj["index_right"]):
                    hit_geoms.setdefault(pnu, []).append(sub.geometry.iloc[ridx])
    df["excl_water"] = 0
    if len(um):
        sj = gpd.sjoin(g, um[["geometry"]].reset_index(drop=True),
                       how="inner", predicate="intersects")
        df["excl_water"] = df["pnu"].isin(set(sj["pnu"])).astype(int)
        for pnu, ridx in zip(sj["pnu"], sj["index_right"]):
            hit_geoms.setdefault(pnu, []).append(um.geometry.iloc[ridx])
    del d, um
    gc.collect()
    print(f"  제외 태깅 완료 ({time.time()-t0:.0f}s)")

    # ── 군사 (파주·김포) ──
    df["excl_mil_control"] = 0
    df["mil_limited"] = 0
    if sgg in MIL_SGG and os.path.exists(MIL_DB):
        mc = sqlite3.connect(MIL_DB)
        mil = pd.read_sql("SELECT pnu, control, limited FROM mil "
                          "WHERE status='OK'", mc)
        mc.close()
        mil["pnu"] = mil["pnu"].astype(str).str.zfill(19)
        mil = mil.drop_duplicates("pnu").set_index("pnu")
        df["excl_mil_control"] = df["pnu"].map(mil["control"]).fillna(0).astype(int)
        df["mil_limited"] = df["pnu"].map(mil["limited"]).fillna(0).astype(int)
        print(f"  군사: 통제 {df['excl_mil_control'].sum():,} / 제한 {df['mil_limited'].sum():,}")

    # ── 기술 제외 (원천 boolean) ──
    for c in ["buildings", "waterbody", "industrialpark"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["excl_tech"] = ((df["buildings"] == 1) | (df["waterbody"] == 1)
                       | (df["industrialpark"] == 1)).astype(int)

    # ── 제한지역 중첩비율 (적중 필지만) ──
    df["restrict_overlap_ratio"] = 0.0
    if hit_geoms:
        gi = g.set_index("pnu")
        ratios = {}
        for pnu, geoms in hit_geoms.items():
            try:
                parcel = gi.geometry.get(pnu)
                if parcel is None or parcel.is_empty:
                    continue
                u = unary_union(geoms)
                ratios[pnu] = min(1.0, parcel.intersection(u).area / parcel.area)
            except Exception:
                ratios[pnu] = None
        df["restrict_overlap_ratio"] = df["pnu"].map(ratios).fillna(0.0).round(4)
        print(f"  중첩비율: {len(ratios):,}필지 ({time.time()-t0:.0f}s)")
    del g, hit_geoms
    gc.collect()

    # ── 시설재배 (팜맵) ──
    fm = gpd.read_file(os.path.join(GIS, "farm_map_shp", farm_fn),
                       where=f"SUBSTR(PNU_LNM_CD,1,5)='{sgg}'",
                       ignore_geometry=True)
    fm["pnu"] = fm["PNU_LNM_CD"].astype(str).str.zfill(19)
    fma = fm.drop_duplicates("pnu").set_index("pnu")["INTPR_CD"].astype(str)
    df["is_facility"] = (df["pnu"].map(fma) == "04").fillna(False).astype(int)
    del fm
    gc.collect()

    # ── 경사 ──
    sl = gpd.read_file(os.path.join(GIS, "korea_slope.gpkg"),
                       where=f"SUBSTR(PNU_LNM_CD,1,5)='{sgg}'",
                       ignore_geometry=True)
    sl["pnu"] = sl["PNU_LNM_CD"].astype(str).str.zfill(19)
    df["slope_mean"] = df["pnu"].map(sl.groupby("pnu")["slope_mean"].mean())
    # 보강(2026-07-16): 레이어 미적중이어도 실측 slope_mean>15°면 태깅 (경계선 오차 방어)
    df.loc[df["slope_mean"].notna() & (df["slope_mean"] > 15), "excl_slope15"] = 1
    del sl
    gc.collect()
    print(f"  시설재배 {df['is_facility'].sum():,} / 경사충전율 "
          f"{df['slope_mean'].notna().mean()*100:.1f}% ({time.time()-t0:.0f}s)")

    # ── 소유구분 → owner_class ──
    raw_na = df["ownership_name"].isna()
    own = df["ownership_name"].astype(str).str.strip()
    df["owner_class"] = own.map(OWN_MAP)
    df.loc[raw_na | own.isin(["nan", "None", "", "<NA>"]), "owner_class"] = "미확인"
    # 귀속재산(등기 미정리)은 부지 확보 관점 소유 확정 불가 → 미확인 (2026-07-13 확정 결정)
    df.loc[own == "일본인/창씨명등", "owner_class"] = "미확인"
    df["owner_class"] = df["owner_class"].fillna("기타")

    # ── indiv_ratio: 반경 500m 면적가중 개인소유 비율 (미확인 제외) ──
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 5186, always_xy=True)
    x, y = tr.transform(df["lon"].values, df["lat"].values)
    pts = np.column_stack([x, y])
    tree = cKDTree(pts)
    known = df["owner_class"] != "미확인"
    is_priv = (df["owner_class"] == "개인").values.astype(float)
    area = df["area_m2"].values
    w_known = np.where(known.values, area, 0.0)
    w_priv = w_known * is_priv
    pairs = tree.query_ball_point(pts, r=NB_RADIUS_M, workers=-1)
    num = np.array([w_priv[idx].sum() for idx in pairs])
    den = np.array([w_known[idx].sum() for idx in pairs])
    df["indiv_ratio"] = np.where(den > 0, num / den, np.nan).round(4)
    print(f"  indiv_ratio: 평균 {np.nanmean(df['indiv_ratio']):.3f} ({time.time()-t0:.0f}s)")

    # ── 최근접 산단 거리 ──
    cx = pd.read_csv(os.path.join(BASE, "complex_integrated.csv"),
                     encoding="utf-8-sig").dropna(subset=["Center_X", "Center_Y"])
    cxx, cxy = tr.transform(cx["Center_X"].values, cx["Center_Y"].values)
    cx_tree = cKDTree(np.column_stack([cxx, cxy]))
    dist, _ = cx_tree.query(pts, k=1)
    df["dist_complex_km"] = (dist / 1000).round(3)

    # ── 진흥 구분 + 적격 boolean ──
    sub = df["subagpromo_name"].astype(str)
    ag = pd.to_numeric(df["agpromo"], errors="coerce").fillna(0).astype(int)
    df["agpromo_class"] = "비진흥"
    df.loc[ag == 1, "agpromo_class"] = "농업진흥구역"   # 세부 미상 진흥은 구역으로 보수 처리
    df.loc[sub.isin(["농업진흥구역", "UEA110"]), "agpromo_class"] = "농업진흥구역"
    df.loc[sub.isin(["농업보호구역", "UEA120"]), "agpromo_class"] = "농업보호구역"

    # 용도지역 결측 = 보수적 제외 + 플래그 (2026-07-14 확정 규칙.
    # use_zone은 제외 판정에 미사용이나, 결측 필지는 규제 확인 불능으로 보아
    # 전 시나리오(S0·S1·S2) 공통 제외 — s2_eligible에 포함되고 s1은 s2에서 파생)
    uz = df["class1_name"]
    df["use_zone_missing"] = (uz.isna() | uz.astype(str).str.strip()
                              .isin(["", "nan", "None"])).astype(int)

    # 시나리오 체계 (2026-07-16 개편): S0 현행 / S1 특구(주력) / S2 확장
    E = df[COMMON_EXCL].max(axis=1) == 1
    # S0 현행: 진흥·보호·자연환경·시설 제외
    df["s0_eligible"] = ((~E) & (df["excl_nature_zone"] == 0)
                         & (df["agpromo_class"] == "비진흥")
                         & (df["is_facility"] == 0)
                         & (df["use_zone_missing"] == 0)).astype(int)
    # S2 확장: 진흥+보호+자연환경 포함, 시설 포함(재포함)
    df["s2_eligible"] = ((~E) & (df["use_zone_missing"] == 0)).astype(int)
    # S1 특구(주력·기본): S2 − 자연환경보전
    df["s1_eligible"] = (df["s2_eligible"].astype(bool)
                         & (df["excl_nature_zone"] == 0)).astype(int)
    # rooftop 태그 = 팜맵 시설재배(지붕형 별도 계수는 실증값 확보 후 2차 — 지금은 태그만)
    df["rooftop"] = df["is_facility"]

    df["emd_code"] = df["dong_code"].astype(str).str[:8]
    df["jimok"] = df["category"].astype(str).str.zfill(2)
    df["use_zone"] = df["class1_name"]

    keep = ["pnu", "sgg", "sgg_name", "emd_code", "dong_code", "lon", "lat",
            "area_m2", "jimok", "use_zone", "agpromo_class", "owner_class",
            "is_facility", "slope_mean",
            "excl_heritage", "excl_wildlife", "excl_natpark", "excl_baekdu",
            "excl_greenbuf", "excl_village", "excl_slope15", "excl_water",
            "excl_mil_control", "mil_limited", "excl_nature_zone", "excl_tech",
            "restrict_overlap_ratio", "use_zone_missing", "rooftop",
            "s0_eligible", "s1_eligible", "s2_eligible",
            "indiv_ratio", "dist_complex_km"]
    out = df[keep].copy()
    out.to_parquet(os.path.join(FINAL_DIR, f"{sgg}.parquet"), index=False)
    print(f"  [SAVE] {sgg}: S0 {out['s0_eligible'].sum():,} / "
          f"S1 {out['s1_eligible'].sum():,} / S2 {out['s2_eligible'].sum():,} / {len(out):,} "
          f"({time.time()-t0:.0f}s)", flush=True)
    return {"sgg": sgg, "name": name, "n": len(out),
            "s0": int(out["s0_eligible"].sum()),
            "s1": int(out["s1_eligible"].sum()),
            "s2": int(out["s2_eligible"].sum())}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all_nonmil"
    if arg == "all":
        targets = list(SGG)
    elif arg == "all_nonmil":
        targets = [s for s in SGG if s not in MIL_SGG]
    else:
        targets = arg.split(",")
    res = []
    for sgg in targets:
        try:
            res.append(process(sgg))
        except Exception as e:
            import traceback
            print(f"[ERR] {sgg}: {e}")
            traceback.print_exc()
    print("\n== 요약 ==")
    print(pd.DataFrame(res).to_string(index=False))
