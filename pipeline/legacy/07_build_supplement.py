# -*- coding: utf-8 -*-
"""07_build_supplement.py — 지목 결측 복구 Phase C-1: 보충 데이터셋 생성
=================================================================
원천(Base gpkg·Land DB)은 수정하지 않는다. 대신 02가 함께 읽을 보충본을 만든다.

입력:  pipeline_out/nojimok_repair/ladfrl.sqlite (repair: 지목, geom: 폴리곤)
       Land_Processed/{sgg}.db (복구 필지의 기존 속성 — 소유·용도·진흥 등)
       pipeline_out/coverage_geom_errors.csv (좌표 오류 83건 — geometry 교체)
       pipeline_out/parcels_clean/{sgg}.parquet (좌표 오류·중복 필지의 속성 재사용)
출력:  pipeline_out/nojimok_repair/supplement/{sgg}.parquet   (parcels_clean 스키마)
       pipeline_out/nojimok_repair/supplement/{sgg}_geom.gpkg (EPSG:5186 폴리곤)
       pipeline_out/nojimok_repair/supplement/drop_pnu.csv    (재측정 후 100㎡ 미만 제외)
       pipeline_out/nojimok_repair/phaseC_summary.md

사용:  python 07_build_supplement.py
"""
import os, sys, io, sqlite3, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import shape

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
REPAIR_DB = os.path.join(OUT, "nojimok_repair", "ladfrl.sqlite")
LAND = os.path.join(BASE, "Land_Processed", "Land_Processed")
CLEAN = os.path.join(OUT, "parcels_clean")
SUPP = os.path.join(OUT, "nojimok_repair", "supplement")
os.makedirs(SUPP, exist_ok=True)

VWORLD_KEY = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
DATA_URL = "https://api.vworld.kr/req/data"

# 정정 라벨 (44131=동남구, 44133=서북구 — 행정표준코드 확인 2026-07-13)
SGG = {"44270": "당진", "44180": "보령", "44200": "아산", "44131": "천안동남",
       "44133": "천안서북", "44210": "서산", "44800": "홍성", "41590": "화성",
       "41220": "평택", "41463": "용인", "41271": "안산", "41390": "시흥",
       "41500": "이천", "41480": "파주", "41570": "김포"}
FARM_NM_TO_CD = {"전": "01", "답": "02", "과수원": "03"}
# ladfrl posesnSeCodeNm → Land DB ownership_name 어휘
POSESN_MAP = {"개인": "개인", "국유지": "국유지", "시/도유지": "시/도유지", "시,도유지": "시/도유지",
              "군유지": "군유지", "법인": "법인", "종중": "종중", "종교단체": "종교단체",
              "외국인": "외국인/외국공공기관", "외국공공기관·단체": "외국인/외국공공기관",
              "기타단체": "기타단체", "지방자치단체": "지방자치단체"}
LAND_COLS = ["pnu", "region", "category", "category_name", "class1", "class1_name",
             "class1_group", "use", "use_name", "ownership", "ownership_name",
             "agpromo", "subagpromo", "subagpromo_name", "planned", "buffer",
             "buildings", "waterbody", "industrialpark", "calculatedarea"]
CLEAN_COLS = LAND_COLS + ["area_m2", "lon", "lat", "dong_code", "sgg", "sgg_name"]


def fetch_geom(session, pnu):
    r = session.get(DATA_URL, params={"service": "data", "request": "GetFeature",
                                      "data": "LP_PA_CBND_BUBUN", "key": VWORLD_KEY,
                                      "attrFilter": f"pnu:=:{pnu}", "crs": "EPSG:4326",
                                      "format": "json", "domain": "localhost"}, timeout=15)
    j = r.json()["response"]
    if j.get("status") != "OK":
        return None
    feats = j["result"]["featureCollection"]["features"]
    return json.dumps(feats[0]["geometry"], separators=(",", ":")) if feats else None


def main():
    t0 = time.time()
    conn = sqlite3.connect(REPAIR_DB)

    # ── 좌표 오류 83건 geometry 확보 (geom 테이블에 병합) ──
    fix = pd.read_csv(os.path.join(OUT, "coverage_geom_errors.csv"), dtype=str)
    fix["pnu"] = fix["pnu"].str.zfill(19)
    have = set(p for (p,) in conn.execute("SELECT pnu FROM geom WHERE status='OK'"))
    todo = [p for p in fix["pnu"] if p not in have]
    if todo:
        print(f"좌표 오류 필지 geometry 재수집: {len(todo)}건")
        s = requests.Session()
        for p in todo:
            gj = None
            try:
                gj = fetch_geom(s, p)
            except Exception:
                pass
            conn.execute("INSERT OR REPLACE INTO geom VALUES (?,?,?,?,?)",
                         (p, "OK" if gj else "NOTFOUND", gj, None, None))
            time.sleep(0.1)
        conn.commit()

    # ── 대상 목록 ──
    farm = pd.read_sql("SELECT r.pnu, r.lndcgr_cd, r.lndcgr_nm, r.posesn_nm, g.geojson "
                       "FROM repair r JOIN geom g ON g.pnu=r.pnu "
                       "WHERE r.lndcgr_nm IN ('전','답','과수원') AND g.status='OK'", conn)
    fixg = pd.read_sql("SELECT pnu, geojson FROM geom WHERE status='OK'", conn)
    fixg = fixg[fixg["pnu"].isin(set(fix["pnu"]))]
    conn.close()
    farm["sgg"] = farm["pnu"].str[:5]
    fixg["sgg"] = fixg["pnu"].str[:5]
    print(f"복구 농지(geometry 확보) {len(farm):,} / 좌표 교정 {len(fixg):,}")

    drops, summary = [], []
    for sgg, name in SGG.items():
        rows = []
        # (a) 복구 농지: Land DB 속성 + 지목/소유 override
        f = farm[farm["sgg"] == sgg]
        if len(f):
            lc = sqlite3.connect(os.path.join(LAND, f"{sgg}.db"))
            ph = ",".join("?" * len(f))
            land = pd.read_sql(
                f'SELECT {", ".join(LAND_COLS)} FROM "{sgg}" WHERE pnu IN ({ph})',
                lc, params=list(f["pnu"]))
            lc.close()
            land["pnu"] = land["pnu"].astype(str).str.zfill(19)
            land = land.drop_duplicates("pnu").merge(
                f[["pnu", "lndcgr_cd", "lndcgr_nm", "posesn_nm", "geojson"]], on="pnu")
            land["category"] = land["lndcgr_nm"].map(FARM_NM_TO_CD)
            land["category_name"] = land["lndcgr_nm"]
            own_na = land["ownership_name"].isna() | land["ownership_name"].astype(str).str.strip().isin(["", "nan", "None"])
            land.loc[own_na, "ownership_name"] = land.loc[own_na, "posesn_nm"].map(POSESN_MAP)
            rows.append(land.drop(columns=["lndcgr_cd", "lndcgr_nm", "posesn_nm"]))
        # (b) 좌표 교정: 기존 clean 속성 재사용 + geometry 교체
        x = fixg[fixg["sgg"] == sgg]
        if len(x):
            cl = pd.read_parquet(os.path.join(CLEAN, f"{sgg}.parquet"))
            cl["pnu"] = cl["pnu"].astype(str).str.zfill(19)
            keep = cl[cl["pnu"].isin(set(x["pnu"]))][LAND_COLS].copy()
            keep = keep.merge(x[["pnu", "geojson"]], on="pnu")
            rows.append(keep)
        if not rows:
            continue
        sup = pd.concat(rows, ignore_index=True).drop_duplicates("pnu")

        # geometry 파싱 → 5186 면적·대표점 (01_clean R3~R5 동일 규칙)
        geoms = [shape(json.loads(gj)) for gj in sup["geojson"]]
        g = gpd.GeoDataFrame(sup.drop(columns="geojson"), geometry=geoms, crs=4326)
        inv = ~g.geometry.is_valid
        if inv.any():
            g.loc[inv, "geometry"] = g.loc[inv, "geometry"].buffer(0)
        g = g[~(g.geometry.isna() | g.geometry.is_empty)].copy()
        g5 = g.to_crs(epsg=5186)
        g["area_m2"] = g5.geometry.area
        small = g["area_m2"] < 100.0
        if small.any():
            drops.extend(g.loc[small, "pnu"].tolist())
            g, g5 = g[~small].copy(), g5[~small.values].copy()
        pts = gpd.GeoSeries(g5.geometry.representative_point(), crs=5186).to_crs(4326)
        g["lon"], g["lat"] = pts.x.values, pts.y.values
        g["dong_code"] = g["region"].astype(str).str.zfill(10)
        g["sgg"], g["sgg_name"] = sgg, name

        pd.DataFrame(g.drop(columns="geometry"))[CLEAN_COLS].to_parquet(
            os.path.join(SUPP, f"{sgg}.parquet"), index=False)
        gpd.GeoDataFrame(g[["pnu"]], geometry=g5.geometry.values, crs=5186).to_file(
            os.path.join(SUPP, f"{sgg}_geom.gpkg"), driver="GPKG")
        n_farm = len(f)
        summary.append({"sgg": sgg, "name": name, "복구농지": n_farm,
                        "좌표교정": len(x), "보충계": len(g)})
        print(f"  {sgg} {name}: 복구 {n_farm:,} + 교정 {len(x)} → 보충 {len(g):,}")

    pd.DataFrame({"pnu": drops}).to_csv(os.path.join(SUPP, "drop_pnu.csv"),
                                        index=False, encoding="utf-8-sig")
    sm = pd.DataFrame(summary)
    with open(os.path.join(OUT, "nojimok_repair", "phaseC_summary.md"), "w", encoding="utf-8") as fp:
        fp.write("# Phase C-1 보충 데이터셋\n\n```\n" + sm.to_string(index=False)
                 + f"\n```\n\n- 재측정 100㎡ 미만 제외: {len(drops)}건 (drop_pnu.csv)\n"
                 f"- 합계 보충: {sm['보충계'].sum():,}\n")
    print(f"\n합계 {sm['보충계'].sum():,} / <100㎡ 제외 {len(drops)} / {(time.time()-t0)/60:.1f}분")


if __name__ == "__main__":
    main()
