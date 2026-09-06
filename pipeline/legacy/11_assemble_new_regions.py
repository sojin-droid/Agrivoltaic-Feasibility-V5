# -*- coding: utf-8 -*-
"""11_assemble_new_regions.py — 신규 4개 지역 원장 조립 (A안)
=================================================================
원천: LX Land DB 4개 (zip에서 추출한 작업본 — zip이 원본으로 보존됨)
      + V-World 수집분 (pipeline_out/new_regions/collect.sqlite)
모드:
  farm : FARM_MERGED_FINAL.shp에서 4개 지역 팜맵 재추출 → FARM_NEW.gpkg (느림, 병행)
  main : ① LX 작업본 패치 (무지목→WFS 지목, 소유 결측→수집 posesn)
         ② Base/{sgg}.gpkg 구축 (LX 전답과 ∩ V-World geometry)
         ③ UM710(상수원) 신규 지역 bbox 수집 → um710_new.gpkg
사용: python 11_assemble_new_regions.py [farm|main]
"""
import os, sys, io, json, sqlite3, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import shape

BASE = r"C:\Users\user\새 폴더"
LAND = os.path.join(BASE, "Land_Processed", "Land_Processed")
CADASTRE = os.path.join(BASE, "Base", "Base")
NR = os.path.join(BASE, "pipeline_out", "new_regions")
COLLECT = os.path.join(NR, "collect.sqlite")
VK = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
SGGS = {"44810": "예산", "41461": "용인처인", "41465": "용인수지", "41273": "안산단원"}
REPAIR_DB = None  # A 지역은 무지목 보완을 이미 반영(당시 collect.sqlite jimok)
if os.environ.get("B_REGIONS") == "1":  # 2026-07-16 B 완전본 재구축
    SGGS = {"28200": "인천남동", "46230": "광양", "46130": "여수", "47111": "포항남",
            "47113": "포항북", "47190": "구미", "31110": "울산중", "31140": "울산남",
            "31170": "울산동", "31200": "울산북", "31710": "울주"}
    COLLECT = os.path.join(NR, "collect_b.sqlite")
    REPAIR_DB = os.path.join(BASE, "pipeline_out", "nojimok_repair", "ladfrl_B.sqlite")
NEW_SIG = {"46230": "12190", "46130": "12130"}  # 전남 개편 — 경계 조회 폴백
FARM_CD = ("01", "02", "03")
POSESN_MAP = {"개인": "개인", "국유지": "국유지", "시/도유지": "시/도유지", "시,도유지": "시/도유지",
              "군유지": "군유지", "법인": "법인", "종중": "종중", "종교단체": "종교단체",
              "외국인": "외국인/외국공공기관", "외국공공기관·단체": "외국인/외국공공기관",
              "기타단체": "기타단체", "지방자치단체": "지방자치단체"}


def mode_farm():
    src = os.path.join(BASE, "GIS_DATA", "farm_map_shp", "FARM_MERGED_FINAL.shp")
    out = os.path.join(BASE, "GIS_DATA", "farm_map_shp", "FARM_NEW.gpkg")
    codes = "','".join(SGGS)
    t0 = time.time()
    print("FARM_MERGED_FINAL 단일 스캔 추출 시작 (수 분~수십 분)", flush=True)
    d = gpd.read_file(src, where=f"SUBSTR(PNU_LNM_CD,1,5) IN ('{codes}')")
    d.to_file(out, driver="GPKG")
    print(f"FARM_NEW.gpkg 저장: {len(d):,}건 ({(time.time()-t0)/60:.1f}분)")
    print(d["PNU_LNM_CD"].astype(str).str[:5].value_counts().to_string())


def mode_main():
    cc = sqlite3.connect(COLLECT)
    wfs = pd.read_sql("SELECT pnu, jimok_cd, jimok_nm, posesn_nm, geojson FROM parcels", cc)
    cc.close()
    wfs = wfs.set_index("pnu")

    for sgg, nm in SGGS.items():
        db = os.path.join(LAND, f"{sgg}.db")
        conn = sqlite3.connect(db)
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{sgg}_pnu ON "{sgg}"(pnu)')
        conn.commit()
        land = pd.read_sql(f'SELECT pnu, category, ownership_name FROM "{sgg}"', conn)
        land["pnu_n"] = land["pnu"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(19)

        # ① 무지목 → WFS 지번 파싱 지목 (+B: ladfrl 회수분 우선)
        na_cat = land["category"].isna() | (land["category"].astype(str).str.strip() == "")
        fill = land.loc[na_cat, "pnu_n"].map(wfs["jimok_cd"])
        fill_nm = land.loc[na_cat, "pnu_n"].map(wfs["jimok_nm"])
        if REPAIR_DB and os.path.exists(REPAIR_DB):
            rc = sqlite3.connect(REPAIR_DB)
            rep = pd.read_sql("SELECT pnu, lndcgr_cd, lndcgr_nm FROM repair WHERE status='OK'", rc)
            rc.close()
            rep = rep.set_index("pnu")
            f2 = land.loc[na_cat, "pnu_n"].map(rep["lndcgr_cd"])
            f2n = land.loc[na_cat, "pnu_n"].map(rep["lndcgr_nm"])
            fill = f2.combine_first(fill)      # 대장 회수 우선, WFS 파싱 폴백
            fill_nm = f2n.combine_first(fill_nm)
        n_fill = int(fill.notna().sum())
        upd = [(c, n, p) for c, n, p in zip(fill, fill_nm, land.loc[na_cat, "pnu"])
               if pd.notna(c)]
        conn.executemany(f'UPDATE "{sgg}" SET category=?, category_name=? WHERE pnu=?', upd)
        # ② 소유 결측 → 수집 posesn
        na_own = land["ownership_name"].isna() | land["ownership_name"].astype(str).str.strip().isin(["", "nan", "None"])
        po = land.loc[na_own, "pnu_n"].map(wfs["posesn_nm"]).map(POSESN_MAP)
        upd2 = [(v, p) for v, p in zip(po, land.loc[na_own, "pnu"]) if pd.notna(v)]
        conn.executemany(f'UPDATE "{sgg}" SET ownership_name=? WHERE pnu=?', upd2)
        conn.commit()

        # ③ Base gpkg: (패치 후) 전답과 ∩ geometry
        cat = pd.read_sql(f'SELECT pnu, category FROM "{sgg}"', conn)
        conn.close()
        cat["pnu_n"] = cat["pnu"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(19)
        farm = cat[cat["category"].isin(FARM_CD)]["pnu_n"]
        sub = wfs.reindex(farm.values)
        have = sub["geojson"].notna()
        geoms = [shape(json.loads(g)) for g in sub.loc[have, "geojson"]]
        g = gpd.GeoDataFrame({"pnu": sub.index[have]}, geometry=geoms, crs=4326)
        g.to_file(os.path.join(CADASTRE, f"{sgg}.gpkg"), driver="GPKG")
        print(f"{sgg} {nm}: 무지목보완 {n_fill:,}/{int(na_cat.sum()):,} / "
              f"소유보완 {len(upd2):,}/{int(na_own.sum()):,} / "
              f"LX전답과 {len(farm):,} → Base {len(g):,} (geometry 무 {int((~have).sum()):,})",
              flush=True)

    # ④ UM710 상수원 — 지역 bbox 수집
    S = requests.Session()
    feats_all = []
    for sgg in SGGS:
        filt = (f"<ogc:Filter xmlns:ogc='http://www.opengis.net/ogc'><ogc:PropertyIsEqualTo>"
                f"<ogc:PropertyName>sig_cd</ogc:PropertyName><ogc:Literal>{NEW_SIG.get(sgg, sgg)}</ogc:Literal>"
                f"</ogc:PropertyIsEqualTo></ogc:Filter>")
        r = S.get("https://api.vworld.kr/req/wfs", params={
            "service": "WFS", "version": "1.1.0", "request": "GetFeature",
            "typename": "lt_c_adsigg", "key": VK, "outputFormat": "application/json",
            "maxFeatures": 5, "domain": "localhost", "srsName": "EPSG:4326",
            "filter": filt}, timeout=30)
        gg = gpd.GeoDataFrame.from_features(r.json().get("features", []), crs=4326)
        if not len(gg):
            print(f"  {sgg} 경계 조회 실패 — UM710 스킵"); continue
        minx, miny, maxx, maxy = gg.total_bounds
        page = 1
        while True:
            r2 = S.get("https://api.vworld.kr/req/data", params={
                "service": "data", "request": "GetFeature", "data": "LT_C_UM710",
                "key": VK, "geomFilter": f"BOX({minx},{miny},{maxx},{maxy})",
                "numOfRows": 1000, "pageNo": page, "domain": "localhost"}, timeout=30)
            resp = r2.json().get("response", {})
            if resp.get("status") != "OK":
                break
            fs = resp.get("result", {}).get("featureCollection", {}).get("features", [])
            feats_all.extend(fs)
            if page >= int(resp.get("page", {}).get("total", 1)):
                break
            page += 1
        time.sleep(0.2)
    if feats_all:
        um = gpd.GeoDataFrame.from_features(feats_all, crs=3857)  # data API 기본 3857
        um_name = "um710_b.gpkg" if os.environ.get("B_REGIONS") == "1" else "um710_new.gpkg"
        um.to_file(os.path.join(NR, um_name), driver="GPKG")
        print(f"UM710: {len(um):,}건 → {um_name}")
    else:
        print("UM710 신규 지역: 적중 0 (파일 미생성 — 02는 기존 레이어만 사용)")


if __name__ == "__main__":
    (mode_farm if (len(sys.argv) > 1 and sys.argv[1] == "farm") else mode_main)()
