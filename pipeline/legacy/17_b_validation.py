# -*- coding: utf-8 -*-
"""17_b_validation.py — T1 검증: B 지역 11개 코드 커버리지 대조 + 원장 품질
지적통계(2024-12-31) 전답과 기준값 vs LX 전답과 vs 원장(팜맵 geometry 확보·정제 후).
도시 지역 농지 희소는 '정상(도시)'로 구분 표기."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
NAMES = {"28200": ("인천남동", "인천광역시 남동구"), "46230": ("광양", "전라남도 광양시"),
         "46130": ("여수", "전라남도 여수시"), "47111": ("포항남", "경상북도 포항시 남구"),
         "47113": ("포항북", "경상북도 포항시 북구"), "47190": ("구미", "경상북도 구미시"),
         "31110": ("울산중", "울산광역시 중구"), "31140": ("울산남", "울산광역시 남구"),
         "31170": ("울산동", "울산광역시 동구"), "31200": ("울산북", "울산광역시 북구"),
         "31710": ("울주", "울산광역시 울주군")}

raw = pd.read_csv(os.path.join(OUT, "jijeok_stats_20241231.csv"), encoding="cp949")
build = pd.read_csv(os.path.join(OUT, "b_regions_build.csv"), dtype={"sgg": str}).set_index("sgg")

rows = []
for sgg, (nm, off_nm) in NAMES.items():
    sub = raw[raw["행정구역"] == off_nm]
    base_farm = int(sub[sub["지목"].isin(["전", "답", "과수원"])]["지번수"].sum())
    base_all = int(sub["지번수"].sum())
    b = build.loc[sgg]
    fin = pd.read_parquet(os.path.join(OUT, "parcels_final", f"{sgg}.parquet"),
                          columns=["s0_eligible", "s2_eligible", "area_m2"])
    urban = "도시(농지 희소 정상)" if base_farm < 15000 else ""
    rows.append({"sgg": sgg, "name": nm, "공식전답과": base_farm,
                 "LX전답과": int(b["LX전답과"]),
                 "LX커버%": round(b["LX전답과"] / base_farm * 100, 1) if base_farm else None,
                 "원장(팜맵geo)": int(b["원장"]),
                 "geo확보%": b["geometry확보%"],
                 "원장/공식%": round(b["원장"] / base_farm * 100, 1) if base_farm else None,
                 "S3적격": int(fin.s2_eligible.sum()),
                 "S3_MW": round(fin[fin.s2_eligible == 1].area_m2.sum() * 0.045 / 1000),
                 "무지목": int(b["무지목"]), "명칭": b["명칭일치"], "비고": urban})
d = pd.DataFrame(rows)
print(d.to_string(index=False))
d.to_csv(os.path.join(OUT, "b_regions_coverage.csv"), index=False, encoding="utf-8-sig")
print("\n합계: 공식", d["공식전답과"].sum(), "/ LX", d["LX전답과"].sum(),
      f"({d['LX전답과'].sum()/d['공식전답과'].sum()*100:.1f}%) / 원장",
      d["원장(팜맵geo)"].sum(), f"({d['원장(팜맵geo)'].sum()/d['공식전답과'].sum()*100:.1f}%)")
# 완전 수집 견적 (연속지적 WFS 프리픽스 스윕): 콜 ≈ 전체지번/1000×1.4
allj = raw[raw["행정구역"].isin([v[1] for v in NAMES.values()])]["지번수"].sum()
print(f"연속지적 완전 수집 시 예상 WFS 콜: ~{int(allj/1000*1.4):,} (전체 지번 {int(allj):,})")
