# -*- coding: utf-8 -*-
"""09c_sgg_summary.py — 시군 요약 카드 산출 (data_contract: sgg_summary 스키마)
=================================================================
검수 지도와 향후 웹 시군 상세가 같은 산출을 읽는다 (pipeline_out/sgg_summary.json).
스키마 (decisions_log 2026-07-14 등록):
  s0_n, s0_mw, s3_n, s3_mw, s3_over_s0          ① 잠재량 총량 (하한 미적용·소유 무관)
  s0_gen_gwh, s3_gen_gwh (MW×8760×0.15/1000)
  demand_gwh_3yr (한전 3개년 평균 — null=수집 예정), demand_note
  s0_demand_pct, s3_demand_pct
  listed_n, listed_mw, listed_share_pct          ③ 공공·법인 소유 중심 후보
    (t=0.30 병합, ≥3MW 공식, 미확인 ≤20%)
  dist_complex_median_km, dist_complex_min_km (등재 지구 최근접 산단 거리)
  main_complexes[] (시군 내 등재 산단명) / complex_covered (bool — 미커버 시 산정 예정)
"""
import os, sys, io, json, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import numpy as np

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
KW_PER_M2 = 0.045
CF = 8760 * 0.15
UNK_TH = 0.20
MIN_MW = 3.0
DEMAND_NOTE = "시군 연간 전력수요는 시군구 전체 업종 합산치(한전 3개년 평균) 기준"

cx = pd.read_csv(os.path.join(BASE, "complex_integrated.csv"), encoding="utf-8-sig")
DEMAND = json.load(open(os.path.join(OUT, "kepco_demand.json"), encoding="utf-8"))
DEM_SRC = DEMAND["source_label"] + " / " + DEMAND["period_label"]
SWEEP = json.load(open(os.path.join(OUT, "ownership_sweep_summary.json"), encoding="utf-8")) \
    if os.path.exists(os.path.join(OUT, "ownership_sweep_summary.json")) else {}

summary = {}
for f in sorted(glob.glob(os.path.join(OUT, "clusters", "*_clusters_S3_t30_merged.json"))):
    sgg = os.path.basename(f)[:5]
    pf = pd.read_parquet(os.path.join(OUT, "parcels_final", f"{sgg}.parquet"),
                         columns=["pnu", "area_m2", "s0_eligible", "s2_eligible",
                                  "dist_complex_km", "lon", "lat"])
    s0 = pf[pf.s0_eligible == 1]
    s3 = pf[pf.s2_eligible == 1]
    s0_mw = s0.area_m2.sum() * KW_PER_M2 / 1000
    s3_mw = s3.area_m2.sum() * KW_PER_M2 / 1000

    j = json.load(open(f, encoding="utf-8"))
    # 공식 = exec_mw>0 / 집계 = exec_mw(≥3MW 연접 블록 합산, 파편 제외 — 2026-07-15 확정)
    listed = [c for c in j["clusters"]
              if c.get("official") and c["unknown_owner_ratio"] <= UNK_TH]
    listed_mw = sum(c["exec_mw"] for c in listed)
    # 등재 지구 산단 거리: 구성 필지 dist_complex_km 중앙값(지구별) → 시군 요약
    mem = json.load(open(f.replace("_clusters_", "_members_"), encoding="utf-8"))
    dmap = pf.set_index("pnu")["dist_complex_km"]
    dists = []
    for c in listed:
        md = dmap.reindex(mem[str(c["cluster_id"])]).median()
        if pd.notna(md):
            dists.append(float(md))
    # 시군 내 등재 산단 (좌표 기반 — CSV SGG_CD 라벨 오류 회피)
    lon0, lon1 = pf.lon.min() - 0.01, pf.lon.max() + 0.01
    lat0, lat1 = pf.lat.min() - 0.01, pf.lat.max() + 0.01
    inb = cx[(cx.Center_X >= lon0) & (cx.Center_X <= lon1)
             & (cx.Center_Y >= lat0) & (cx.Center_Y <= lat1)]
    main = inb.sort_values("Peak_Demand_MW", ascending=False)["Complex_Name"].head(3).tolist()

    summary[sgg] = {
        "s0_n": int(len(s0)), "s0_mw": round(s0_mw, 1),
        "s3_n": int(len(s3)), "s3_mw": round(s3_mw, 1),
        "s3_over_s0": round(s3_mw / s0_mw, 2) if s0_mw else None,
        "s0_gen_gwh": round(s0_mw * CF / 1000, 1),
        "s3_gen_gwh": round(s3_mw * CF / 1000, 1),
        "demand_gwh_3yr": (dm := DEMAND["by_code"].get(sgg, {})).get("total_gwh_year"),
        "demand_scope": dm.get("scope"),
        "demand_note": DEMAND_NOTE + (f" — 수요 범위: {dm['scope']}" if dm.get("scope") and "전체(" in dm["scope"] else ""),
        "demand_source": DEM_SRC,
        "s0_demand_pct": (round(s0_mw * CF / 1000 / dm["total_gwh_year"] * 100, 1)
                          if dm.get("total_gwh_year") else None),
        "s3_demand_pct": (round(s3_mw * CF / 1000 / dm["total_gwh_year"] * 100, 1)
                          if dm.get("total_gwh_year") else None),
        "listed_n": len(listed), "listed_mw": round(listed_mw, 1),
        "listed_share_pct": round(listed_mw / s3_mw * 100, 1) if s3_mw else None,
        # 특구 지정 가능성 (2026-07-15): b=공식(블록≥3MW)∧미확인≤20% 합산 MW
        "designation_status": (sw := SWEEP.get(sgg, {})).get("status_t30"),
        "pct_of_50mw": round(sw["b_mw_t30"] / 50 * 100) if sw.get("b_mw_t30") is not None else None,
        "threshold_t_50": sw.get("threshold_t_50"), "threshold_t_100": sw.get("threshold_t_100"),
        "official_n_ref": j["summary"].get("n_clusters_official"),
        "official_mw_ref": j["summary"].get("mw_official"),
        "dist_complex_median_km": round(float(np.median(dists)), 1) if dists else None,
        "dist_complex_min_km": round(float(np.min(dists)), 1) if dists else None,
        "main_complexes": main,
        "complex_covered": bool(len(inb)),
        "criteria": {"listed": f">= {MIN_MW}MW & unknown_owner_ratio <= {UNK_TH}",
                     "t": 0.30, "scenario": "S3", "merge": "P95"},
    }
    print(f"{sgg}: S0 {len(s0):,}필지 {s0_mw:,.0f}MW / S3 {len(s3):,} {s3_mw:,.0f}MW / "
          f"등재 {len(listed)}지구 {listed_mw:,.0f}MW ({summary[sgg]['listed_share_pct']}%) / "
          f"산단 {'∅ 산정예정' if not len(inb) else ','.join(main[:2])}")

with open(os.path.join(OUT, "sgg_summary.json"), "w", encoding="utf-8") as fp:
    json.dump(summary, fp, ensure_ascii=False, indent=1)
print(f"\nsgg_summary.json — {len(summary)}개 시군")
