# -*- coding: utf-8 -*-
"""13_block_metrics.py — 지구 연접 블록 지표 + 공식 재정의 + 시군 판정 스윕
=================================================================
입력: pipeline_out/clusters/{sgg}_clusters_S3_t{10..50}_merged.json (+members)
처리 (2026-07-15 확정):
  - 블록 = 편입 필지 union, 접합 25m(양측 12.5m 버퍼) 기준 연속 덩어리
  - 지구 필드 추가: block_count, max_block_mw, max_block_share,
    official(최대 연접 블록 ≥3MW — 명목 MW 기준 폐기)
  - summary 갱신: n_clusters_official / mw_official (블록 기준)
출력: pipeline_out/ownership_sweep_summary.json
  {sgg: {"by_t": {t: {official_n, official_mw, b_n, b_mw}},
         "threshold_t_50", "threshold_t_100", "status_t30"}}
  b = 공식 지구 ∧ 미확인 ≤20% (특구 지정 가능성 지표) / official = 참고치
판정선: <50 미달 / 50~100 지정 가능 / ≥100 유력
사용: python 13_block_metrics.py [sgg콤마 | all]
"""
import os, sys, io, json, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from shapely.strtree import STRtree

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
CL_DIR = os.environ.get("CLUSTER_DIR", os.path.join(OUT, "clusters"))  # 비교 분석용 대체 가능
JOIN_M = 25.0          # 블록 접합 거리 (확정 2026-07-16 결정로그 — 18_block_production과 동일값. 본 스크립트는 구 04 클러스터 입력 기반 구세대)
OFFICIAL_BLOCK_MW = 3.0
UNK_TH = 0.20
TS = [10, 20, 30, 40, 50]
KW_PER_M2 = 0.045


def load_geoms(sgg, need):
    g = gpd.read_file(os.path.join(BASE, "Base", "Base", f"{sgg}.gpkg"))
    pc = next(c for c in g.columns if c.lower() == "pnu")
    g = g.rename(columns={pc: "pnu"})[["pnu", "geometry"]]
    g["pnu"] = g["pnu"].astype(str).str.zfill(19)
    g = g[g["pnu"].isin(need)].to_crs(epsg=5186)
    sp = os.path.join(OUT, "nojimok_repair", "supplement", f"{sgg}_geom.gpkg")
    if os.path.exists(sp):
        s = gpd.read_file(sp)[["pnu", "geometry"]]
        s["pnu"] = s["pnu"].astype(str).str.zfill(19)
        s = s[s["pnu"].isin(need)].to_crs(epsg=5186)
        g = pd.concat([g[~g["pnu"].isin(set(s["pnu"]))], s], ignore_index=True)
    return dict(zip(g["pnu"], g["geometry"]))


def blocks_of(geoms):
    """반환: 블록별 필지 면적 합 배열 (㎡)"""
    u = unary_union([x.buffer(JOIN_M / 2) for x in geoms])
    bl = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    tree = STRtree(bl)
    ba = np.zeros(len(bl))
    for x in geoms:
        rp = x.representative_point()
        for i in tree.query(rp):
            if bl[i].intersects(rp):
                ba[i] += x.area
                break
    return ba


def process(sgg):
    files = {t: os.path.join(CL_DIR, f"{sgg}_clusters_S3_t{t}_merged.json") for t in TS}
    mems = {t: os.path.join(CL_DIR, f"{sgg}_members_S3_t{t}_merged.json") for t in TS}
    need = set()
    for t in TS:
        if os.path.exists(mems[t]):
            m = json.load(open(mems[t], encoding="utf-8"))
            j = json.load(open(files[t], encoding="utf-8"))
            for c in j["clusters"]:
                if c["mw"] >= OFFICIAL_BLOCK_MW:
                    need.update(m[str(c["cluster_id"])])
    gm = load_geoms(sgg, need)
    by_t = {}
    for t in TS:
        if not os.path.exists(files[t]):
            continue
        j = json.load(open(files[t], encoding="utf-8"))
        m = json.load(open(mems[t], encoding="utf-8"))
        off_n = off_mw = off_mw_nom = b_n = b_mw = 0
        for c in j["clusters"]:
            if c["mw"] < OFFICIAL_BLOCK_MW:
                c["block_count"] = None
                c["max_block_mw"] = None
                c["max_block_share"] = None
                c["exec_mw"] = 0.0
                c["exec_blocks"] = 0
                c["official"] = False
                continue
            geoms = [gm[p] for p in m[str(c["cluster_id"])] if p in gm]
            ba = blocks_of(geoms)
            bmw = ba * KW_PER_M2 / 1000
            qual = bmw[bmw >= OFFICIAL_BLOCK_MW]
            c["block_count"] = int(len(ba))
            c["max_block_mw"] = round(float(bmw.max()), 2)
            c["max_block_share"] = round(float(ba.max() / ba.sum()), 3) if ba.sum() else 0
            # 실행 MW = ≥3MW 연접 블록 합산 — 파편 필지는 집계 제외 (2026-07-15 확정)
            c["exec_mw"] = round(float(qual.sum()), 2)
            c["exec_blocks"] = int(len(qual))
            c["official"] = c["exec_mw"] > 0
            if c["official"]:
                off_n += 1
                off_mw += c["exec_mw"]
                off_mw_nom += c["mw"]
                if c["unknown_owner_ratio"] <= UNK_TH:
                    b_n += 1
                    b_mw += c["exec_mw"]
        j["summary"]["n_clusters_official"] = off_n
        j["summary"]["mw_official"] = round(off_mw, 1)          # 실행 MW (블록 합산)
        j["summary"]["mw_official_nominal"] = round(off_mw_nom, 1)  # 참고: 명목 합
        j["summary"]["official_rule"] = (f"exec_mw = Σ(연접블록 ≥{OFFICIAL_BLOCK_MW}MW), "
                                         f"JOIN {JOIN_M}m — 파편 제외")
        json.dump(j, open(files[t], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        by_t[f"0.{t}"] = {"official_n": off_n, "official_mw": round(off_mw, 1),
                          "b_n": b_n, "b_mw": round(b_mw, 1)}
    th50 = next((k for k in sorted(by_t) if by_t[k]["b_mw"] >= 50), "미달")
    th100 = next((k for k in sorted(by_t) if by_t[k]["b_mw"] >= 100), "미달")
    b30 = by_t.get("0.30", {}).get("b_mw", 0)
    status = "유력" if b30 >= 100 else ("지정 가능" if b30 >= 50 else "요건 미달")
    print(f"  {sgg}: t0.30 b={b30}MW [{status}] / t50={th50} t100={th100} "
          f"/ by_t={{'{list(by_t)[0]}': {by_t[list(by_t)[0]]['b_mw']} ...}}", flush=True)
    return {"by_t": by_t, "threshold_t_50": th50, "threshold_t_100": th100,
            "status_t30": status, "b_mw_t30": b30,
            "criteria": {"official": f"exec_mw = Σ(연접 블록 ≥{OFFICIAL_BLOCK_MW}MW), 접합 {JOIN_M}m 잠정 — 파편 집계 제외",
                         "b": f"공식 지구(exec_mw>0) ∧ 미확인 ≤{UNK_TH}, exec_mw 합산",
                         "bands": "<50 미달 / 50–100 지정 가능 / ≥100 유력"}}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    sggs = (sorted({os.path.basename(f)[:5] for f in
                    glob.glob(os.path.join(CL_DIR, "*_clusters_S3_t30_merged.json"))})
            if arg == "all" else arg.split(","))
    res = {}
    for s in sggs:
        try:
            res[s] = process(s)
        except Exception as e:
            import traceback
            print(f"[ERR] {s}: {e}")
            traceback.print_exc()
    out = os.environ.get("SWEEP_OUT", os.path.join(OUT, "ownership_sweep_summary.json"))
    if os.path.exists(out):
        old = json.load(open(out, encoding="utf-8"))
        old.update(res)
        res = old
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nownership_sweep_summary.json — {len(res)}개 시군")
