# -*- coding: utf-8 -*-
"""01_clean_parcels.py — 필지 원장 구축 1단계: 조인 감사 + 정제 + 대표점 추출
=================================================================
입력:
  Base/Base/{sgg}.gpkg              연속지적도 전체 필지 (geometry)
  Land_Processed/Land_Processed/{sgg}.db  토지 속성 원장 (전체 지목)
출력:
  pipeline_out/parcels_clean/{sgg}.parquet   정제 필지 (WGS84 대표점 lon/lat, TM 면적)
  pipeline_out/join_audit.csv / cleaning_report.md

사용:
  python 01_clean_parcels.py audit   # PNU 조인 매칭률 + 미매칭 샘플 (속성만, 빠름)
  python 01_clean_parcels.py clean   # 정제 + 대표점 (geometry, 시간 소요)
"""
import os, sys, io, sqlite3, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
CADASTRE = os.path.join(BASE, "Base", "Base")
LAND = os.path.join(BASE, "Land_Processed", "Land_Processed")
OUT_ROOT = os.path.join(BASE, "pipeline_out")
CLEAN_DIR = os.path.join(OUT_ROOT, "parcels_clean")
os.makedirs(CLEAN_DIR, exist_ok=True)

# 주의: 44180=보령, 44210=서산 (구 파이프라인의 서산/예산 라벨은 오류였음.
#       예산군 44810 데이터는 미보유 — council_name으로 검증 완료 2026-07-13)
#       44131=천안동남, 44133=천안서북 (행정표준코드·좌표 검증 2026-07-13 — 구 라벨 스왑 정정)
SGG = {
    "44270": "당진", "44180": "보령", "44200": "아산",
    "44131": "천안동남", "44133": "천안서북", "44210": "서산",
    "44800": "홍성", "41590": "화성", "41220": "평택",
    "41463": "용인", "41271": "안산", "41390": "시흥",
    "41500": "이천", "41480": "파주", "41570": "김포",
    # 2026-07-14 확장 (A안): Base는 11_assemble이 V-World 수집분으로 구축
    "44810": "예산", "41461": "용인처인", "41465": "용인수지", "41273": "안산단원",
    # 2026-07-16 B 지역 완전본 (Base=collect_b WFS geometry, 11_assemble B_REGIONS=1)
    "28200": "인천남동", "46230": "광양", "46130": "여수", "47111": "포항남",
    "47113": "포항북", "47190": "구미", "31110": "울산중", "31140": "울산남",
    "31170": "울산동", "31200": "울산북", "31710": "울주",
}

MIN_AREA_M2 = 100.0
TM_EPSG = 5186


def norm_pnu(s: pd.Series) -> pd.Series:
    """19자리 PNU 문자열 정규화 (숫자화 부작용·leading zero 보존 검증 포함)"""
    s = s.astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)   # float 오염 방지
    return s.str.zfill(19)


def load_land_attrs(sgg: str) -> pd.DataFrame:
    conn = sqlite3.connect(os.path.join(LAND, f"{sgg}.db"))
    df = pd.read_sql(
        f'SELECT pnu, region, category, category_name, class1, class1_name,'
        f' class1_group, use, use_name, ownership, ownership_name,'
        f' agpromo, subagpromo, subagpromo_name, planned, buffer,'
        f' buildings, waterbody, industrialpark, calculatedarea'
        f' FROM "{sgg}"', conn)
    conn.close()
    df["pnu"] = norm_pnu(df["pnu"])
    return df


def load_cadastre_pnu(sgg: str) -> pd.Series:
    """Base gpkg에서 pnu만 (sqlite 직접 조회, geometry 미파싱)"""
    conn = sqlite3.connect(os.path.join(CADASTRE, f"{sgg}.gpkg"))
    t = pd.read_sql("SELECT table_name FROM gpkg_contents WHERE data_type='features'",
                    conn).iloc[0]["table_name"]
    cols = pd.read_sql(f'PRAGMA table_info("{t}")', conn)["name"].tolist()
    pnu_col = next(c for c in cols if c.lower() == "pnu")
    s = pd.read_sql(f'SELECT "{pnu_col}" AS pnu FROM "{t}"', conn)["pnu"]
    conn.close()
    return norm_pnu(s)


def audit():
    rows, samples = [], []
    for sgg, name in SGG.items():
        land = load_land_attrs(sgg)
        cad = load_cadastre_pnu(sgg)
        land_set, cad_set = set(land["pnu"]), set(cad)
        inter = land_set & cad_set
        only_land = sorted(land_set - cad_set)
        only_cad = sorted(cad_set - land_set)
        # 원본 pnu 자릿수 이상 검사
        bad_len = (land["pnu"].str.len() != 19).sum()
        rows.append({
            "sgg": sgg, "name": name,
            "지적필지": len(cad_set), "지적행(중복포함)": len(cad),
            "LandDB필지": len(land_set),
            "매칭": len(inter),
            "매칭률_지적기준_pct": round(len(inter) / len(cad_set) * 100, 2),
            "매칭률_Land기준_pct": round(len(inter) / len(land_set) * 100, 2),
            "지적중복pnu": len(cad) - len(cad_set),
            "PNU자릿수이상": int(bad_len),
            "Land전용": len(only_land), "지적전용": len(only_cad),
        })
        for p in only_land[:5]:
            samples.append({"sgg": name, "side": "LandDB에만", "pnu": p})
        for p in only_cad[:5]:
            samples.append({"sgg": name, "side": "지적에만", "pnu": p})
        print(f"  {sgg} {name}: 지적 {len(cad_set):,} / Land {len(land_set):,} "
              f"/ 매칭 {len(inter):,} ({len(inter)/len(cad_set)*100:.2f}%)")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT_ROOT, "join_audit.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(samples).to_csv(os.path.join(OUT_ROOT, "join_audit_미매칭샘플.csv"),
                                 index=False, encoding="utf-8-sig")
    print("\n[전체]")
    print(f"  지적 {df['지적필지'].sum():,} / Land {df['LandDB필지'].sum():,} "
          f"/ 매칭 {df['매칭'].sum():,}")
    print(df.to_string(index=False))


def clean():
    import geopandas as gpd
    report = ["# cleaning_report.md — 필지 정제 규칙별 제외 건수", ""]
    stats = []
    for sgg, name in SGG.items():
        t0 = time.time()
        land = load_land_attrs(sgg)
        g = gpd.read_file(os.path.join(CADASTRE, f"{sgg}.gpkg"))
        pnu_col = next(c for c in g.columns if c.lower() == "pnu")
        g = g.rename(columns={pnu_col: "pnu"})[["pnu", "geometry"]]
        g["pnu"] = norm_pnu(g["pnu"])
        n0 = len(g)

        # R1. 지적 PNU 중복 제거 (첫 행 유지)
        g = g.drop_duplicates("pnu")
        n_dup = n0 - len(g)

        # R2. Land DB 속성 조인 (inner: 속성 없는 필지는 분석 불가)
        m = g.merge(land.drop_duplicates("pnu"), on="pnu", how="inner")
        n_nojoin = len(g) - len(m)
        m = gpd.GeoDataFrame(m, geometry="geometry", crs=g.crs)

        # R3. invalid geometry 수리 → 실패분 제외
        inv = ~m.geometry.is_valid
        if inv.any():
            m.loc[inv, "geometry"] = m.loc[inv, "geometry"].buffer(0)
        still_bad = m.geometry.isna() | m.geometry.is_empty | (~m.geometry.is_valid)
        n_badgeom = int(still_bad.sum())
        m = m[~still_bad].copy()

        # R4. TM 면적, 100㎡ 미만 제외
        m_tm = m.to_crs(epsg=TM_EPSG)
        m["area_m2"] = m_tm.geometry.area
        small = m["area_m2"] < MIN_AREA_M2
        n_small = int(small.sum())
        m = m[~small].copy()
        m_tm = m_tm[~small.values].copy()

        # R5. 대표점 (TM에서 point_on_surface → WGS84)
        pts = m_tm.geometry.representative_point()
        pts_wgs = gpd.GeoSeries(pts, crs=TM_EPSG).to_crs(epsg=4326)
        m["lon"] = pts_wgs.x.values
        m["lat"] = pts_wgs.y.values

        # 소유구분 결측
        own_na = m["ownership"].isna() | (m["ownership"].astype(str).isin(["nan", "None", ""]))
        m["dong_code"] = m["region"].astype(str).str.zfill(10)
        m["sgg"] = sgg
        m["sgg_name"] = name

        out = m.drop(columns="geometry")
        pd.DataFrame(out).to_parquet(os.path.join(CLEAN_DIR, f"{sgg}.parquet"), index=False)

        stats.append({"sgg": sgg, "name": name, "지적원본": n0,
                      "R1중복": n_dup, "R2속성없음": n_nojoin,
                      "R3geometry불량": n_badgeom, "R4_100m2미만": n_small,
                      "최종": len(m), "소유결측": int(own_na.sum()),
                      "소유결측률_pct": round(own_na.mean() * 100, 2)})
        print(f"  {sgg} {name}: {n0:,} → {len(m):,} "
              f"(중복 {n_dup:,}, 무속성 {n_nojoin:,}, geom {n_badgeom:,}, "
              f"<100㎡ {n_small:,}) {time.time()-t0:.0f}s", flush=True)
        del g, m, m_tm, land

    df = pd.DataFrame(stats)
    df.to_csv(os.path.join(OUT_ROOT, "cleaning_stats.csv"), index=False, encoding="utf-8-sig")
    report.append("```\n" + df.to_string(index=False) + "\n```")
    report.append("")
    report.append(f"- R4 기준: {MIN_AREA_M2:.0f}㎡ 미만 제외 (확정 기준)")
    report.append(f"- 면적: EPSG:{TM_EPSG}(TM) 투영 면적 / 대표점: TM point_on_surface → WGS84 저장")
    with open(os.path.join(OUT_ROOT, "cleaning_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("\ncleaning_report.md 저장")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if len(sys.argv) > 2:  # 시군 부분 실행: python 01_clean_parcels.py clean 44810,41461
        keep = set(sys.argv[2].split(","))
        SGG = {k: v for k, v in SGG.items() if k in keep}
    (audit if mode == "audit" else clean)()
