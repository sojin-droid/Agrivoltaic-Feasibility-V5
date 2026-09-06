# -*- coding: utf-8 -*-
"""15_build_b_regions.py — Phase E1: 전국 거점 11개 코드(B 지역) 원장 구축
=================================================================
원천: LX Land DB(추출본) + 팜맵 FARM_B.gpkg (geometry — 연속지적 API 금지 조건에 따른
      로컬 대체. 팜맵은 실경작 기준이라 지목 농지의 일부만 커버 → 커버리지 표에 명시)
처리: 코드별 ① council_name 코드↔명칭 대조 ② LX 전답과 ∩ 팜맵 geometry
      ③ 정제(R1 중복·R4 <100㎡, area=LX calculatedarea) → parcels_clean parquet
      ④ Base/{sgg}.gpkg(팜맵 필지 dissolve, 5186) — 02 공간 태깅용
사용: python 15_build_b_regions.py [코드콤마 | all]
"""
import os, sys, io, sqlite3, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
import geopandas as gpd

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
LAND = os.path.join(BASE, "Land_Processed", "Land_Processed")
CADASTRE = os.path.join(BASE, "Base", "Base")
FARM_B = os.path.join(BASE, "GIS_DATA", "farm_map_shp", "FARM_B.gpkg")
CLEAN = os.path.join(OUT, "parcels_clean")
LOG = os.path.join(OUT, "b_regions_build_log.md")

SGGS = {"28200": "인천남동", "46230": "광양", "46130": "여수",
        "47111": "포항남", "47113": "포항북", "47190": "구미",
        "31110": "울산중", "31140": "울산남", "31170": "울산동",
        "31200": "울산북", "31710": "울주"}
LAND_COLS = ["pnu", "region", "category", "category_name", "class1", "class1_name",
             "class1_group", "use", "use_name", "ownership", "ownership_name",
             "agpromo", "subagpromo", "subagpromo_name", "planned", "buffer",
             "buildings", "waterbody", "industrialpark", "calculatedarea"]
CLEAN_COLS = LAND_COLS + ["area_m2", "lon", "lat", "dong_code", "sgg", "sgg_name"]
FARM_CD = ("01", "02", "03")
MIN_AREA = 100.0

bjd = pd.read_csv(os.path.join(OUT, "bjd_codes_20250805.csv"), encoding="cp949", dtype=str)
SGG_NM_OFFICIAL = bjd[bjd["법정동코드"].str[5:] == "00000"].set_index(
    bjd[bjd["법정동코드"].str[5:] == "00000"]["법정동코드"].str[:5])["법정동명"]

fm_all = gpd.read_file(FARM_B)
fm_all["pnu"] = fm_all["PNU_LNM_CD"].astype(str).str.zfill(19)
print(f"FARM_B 로드: {len(fm_all):,} 폴리곤", flush=True)

logs = [f"# B 지역 원장 구축 로그 ({time.strftime('%Y-%m-%d %H:%M')})",
        "", "geometry 원천 = 팜맵(실경작 기준) — 연속지적 API 미사용(야간 무인 조건).",
        "지목 농지 중 팜맵 미수록 필지는 원장 제외 → geometry 확보율 명시.", ""]
rows = []
for sgg, nm in (SGGS.items() if len(sys.argv) < 2 or sys.argv[1] == "all"
                else [(s, SGGS[s]) for s in sys.argv[1].split(",")]):
    t0 = time.time()
    try:
        conn = sqlite3.connect(os.path.join(LAND, f"{sgg}.db"))
        land = pd.read_sql(f'SELECT {", ".join(LAND_COLS)}, council_name FROM "{sgg}"', conn)
        conn.close()
        land["pnu"] = land["pnu"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(19)
        # ① 코드↔명칭 대조
        cn = land["council_name"].dropna().astype(str)
        top_cn = cn.value_counts().index[0] if len(cn) else "?"
        official = SGG_NM_OFFICIAL.get(sgg, "?")
        name_ok = any(tok in official for tok in str(top_cn).split()) or str(top_cn) in official
        n_all, n_nocat = len(land), int(land["category"].isna().sum())
        farm = land[land["category"].isin(FARM_CD)].drop_duplicates("pnu")
        # ② 팜맵 geometry
        fm = fm_all[fm_all["pnu"].str[:5] == sgg]
        fm_d = fm.dissolve(by="pnu")
        fac = fm.groupby("pnu")["INTPR_CD"].apply(lambda x: "04" if (x.astype(str) == "04").any() else "00")
        m = farm.merge(fm_d.reset_index()[["pnu", "geometry"]], on="pnu", how="inner")
        m = gpd.GeoDataFrame(m, geometry="geometry", crs=fm_all.crs).to_crs(epsg=5186)
        geo_rate = len(m) / len(farm) * 100 if len(farm) else 0
        # ③ 정제
        m["area_m2"] = pd.to_numeric(m["calculatedarea"], errors="coerce")
        n_area_na = int(m["area_m2"].isna().sum())
        m.loc[m["area_m2"].isna(), "area_m2"] = m.geometry.area[m["area_m2"].isna()]
        small = m["area_m2"] < MIN_AREA
        m = m[~small].copy()
        inv = ~m.geometry.is_valid
        if inv.any():
            m.loc[inv, "geometry"] = m.loc[inv, "geometry"].buffer(0)
        pts = gpd.GeoSeries(m.geometry.representative_point(), crs=5186).to_crs(4326)
        m["lon"], m["lat"] = pts.x.values, pts.y.values
        m["dong_code"] = m["region"].astype(str).str.zfill(10)
        m["sgg"], m["sgg_name"] = sgg, nm
        pd.DataFrame(m.drop(columns=["geometry", "council_name"]))[CLEAN_COLS].to_parquet(
            os.path.join(CLEAN, f"{sgg}.parquet"), index=False)
        gpd.GeoDataFrame({"pnu": m["pnu"]}, geometry=m.geometry.values, crs=5186).to_file(
            os.path.join(CADASTRE, f"{sgg}.gpkg"), driver="GPKG")
        rows.append({"sgg": sgg, "name": nm, "LX전체": n_all, "무지목": n_nocat,
                     "LX전답과": len(farm), "팜맵매칭": len(m) + int(small.sum()),
                     "geometry확보%": round(geo_rate, 1), "<100㎡제외": int(small.sum()),
                     "원장": len(m), "면적결측대체": n_area_na,
                     "council": top_cn, "명칭일치": "OK" if name_ok else "확인필요"})
        logs.append(f"- {sgg} {nm}: LX {n_all:,}(전답과 {len(farm):,}, 무지목 {n_nocat:,}) → "
                    f"팜맵 매칭 {geo_rate:.1f}% → 원장 {len(m):,} "
                    f"(council='{top_cn}' vs 공식 '{official}' {'OK' if name_ok else '불일치!'}) "
                    f"{time.time()-t0:.0f}s")
        print(logs[-1], flush=True)
    except Exception as e:
        import traceback
        logs.append(f"- {sgg} {nm}: **실패** — {e}")
        print(f"[실패] {sgg} {nm}: {e}", flush=True)
        traceback.print_exc()

df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "b_regions_build.csv"), index=False, encoding="utf-8-sig")
logs += ["", "```", df.to_string(index=False), "```"]
open(LOG, "w", encoding="utf-8").write("\n".join(logs))
print(f"\n로그: {LOG}")
