# -*- coding: utf-8 -*-
"""16_join_study.py — T2·T3: 접합 거리 결정 자료 + 50MW 분할 규칙 예시 (당진)
=================================================================
T2: ① 적격 필지 최근접 간격 히스토그램(경계간 거리, 농로·구거 대역 주석)
    ② 접합 15/25/35/50m 각각의 블록 분해 + ≥3MW 세그먼트(3단 분할 적용) 지도 데이터
T3: 각 접합안의 최대 블록에 3단 분할(①법정리 ②소유 경계 ③콤팩트 절단) 적용 통계
출력: pipeline_out/block_proto/join_study.json (지도용) + stdout 표
주의: 결정 자료 생성만 — 채택·확정 기록 금지 (사용자 아침 결정용)
"""
import os, sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union, transform as shp_transform
from shapely.strtree import STRtree
from pyproj import Transformer

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
PROTO = os.path.join(OUT, "block_proto")
SGG = "44270"
KW = 0.045
CAP = 50.0
MIN_MW = 3.0
JOINS = [15, 25, 35, 50]
TRI = Transformer.from_crs(5186, 4326, always_xy=True).transform

pf = pd.read_parquet(os.path.join(OUT, "parcels_final", f"{SGG}.parquet"),
                     columns=["pnu", "s2_eligible", "area_m2", "owner_class", "dong_code"])
pf = pf[pf.s2_eligible == 1].set_index("pnu")
g = gpd.read_file(os.path.join(BASE, "Base", "Base", f"{SGG}.gpkg"))
pc = next(c for c in g.columns if c.lower() == "pnu")
g = g.rename(columns={pc: "pnu"})[["pnu", "geometry"]]
g["pnu"] = g["pnu"].astype(str).str.zfill(19)
g = g[g["pnu"].isin(set(pf.index))].to_crs(epsg=5186)
sp = os.path.join(OUT, "nojimok_repair", "supplement", f"{SGG}_geom.gpkg")
if os.path.exists(sp):
    s = gpd.read_file(sp)[["pnu", "geometry"]]
    s["pnu"] = s["pnu"].astype(str).str.zfill(19)
    s = s[s["pnu"].isin(set(pf.index))].to_crs(epsg=5186)
    g = pd.concat([g[~g["pnu"].isin(set(s["pnu"]))], s], ignore_index=True)
g = g.drop_duplicates("pnu").reset_index(drop=True)
AREA = pf["area_m2"].reindex(g["pnu"]).values
OWN = pf["owner_class"].reindex(g["pnu"]).values
RI = pf["dong_code"].reindex(g["pnu"]).astype(str).str.zfill(10).values
GEOMS = g.geometry.values
REPS = np.array([[p.x, p.y] for p in g.geometry.representative_point()])
N = len(g)
print(f"당진 S3 적격 {N:,}필지", flush=True)

# ── T2① 최근접 간격 히스토그램 (필지 경계 간 거리) ──
t0 = time.time()
tree = STRtree(GEOMS)
near_idx = tree.nearest(GEOMS)  # 자기 자신 반환 가능성 → 검사
gaps = np.zeros(N)
for i in range(N):
    j = near_idx[i]
    if j == i:  # 자기 자신이면 2번째 근접 탐색
        cand = tree.query(GEOMS[i].buffer(120))
        cand = [c for c in cand if c != i]
        if not cand:
            gaps[i] = 120
            continue
        gaps[i] = min(GEOMS[i].distance(GEOMS[c]) for c in cand)
    else:
        gaps[i] = GEOMS[i].distance(GEOMS[j])
gaps = np.clip(gaps, 0, 120)
hist, edges = np.histogram(gaps, bins=list(range(0, 62, 2)) + [120])
pos = gaps[gaps > 0.5]  # 비접촉 필지만
print(f"간격 계산 {time.time()-t0:.0f}s / 직접 접촉(<0.5m) {int((gaps<=0.5).sum()):,} "
      f"({(gaps<=0.5).mean()*100:.0f}%) / 비접촉 중앙값 {np.median(pos):.1f}m "
      f"/ P75 {np.percentile(pos,75):.1f} / P90 {np.percentile(pos,90):.1f}", flush=True)

# ── 블록 분해 유틸 ──
def decompose(idx, join_m):
    sub = GEOMS[idx]
    u = unary_union([x.buffer(join_m / 2) for x in sub])
    bl = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    tr = STRtree(bl)
    asn = np.full(len(idx), -1)
    for k, x in enumerate(sub):
        rp = x.representative_point()
        for i in tr.query(rp):
            if bl[i].intersects(rp):
                asn[k] = i
                break
    return [idx[asn == i] for i in range(len(bl)) if (asn == i).any()]


def split3(ix, join_m):
    """3단 분할: ①법정리 ②소유 경계(그룹 연접) ③콤팩트(주축 누적 용량).
    반환 (세그먼트 목록[(idx, how)], 단계 통계)"""
    stats = {"입력MW": AREA[ix].sum() * KW / 1000, "리분할": 0, "소유분할": 0, "콤팩트": 0}
    if stats["입력MW"] <= CAP:
        return [(ix, "무분할")], stats
    out = []
    for ri in np.unique(RI[ix]):
        p1 = ix[RI[ix] == ri]
        if AREA[p1].sum() * KW / 1000 <= CAP:
            out.append((p1, "①리"))
            continue
        stats["리분할"] += 1
        # ② 소유 경계: owner_class 그룹별 연접 성분
        pending = []
        for grp in np.unique(OWN[p1]):
            p2s = decompose(p1[OWN[p1] == grp], join_m)
            for p2 in p2s:
                if AREA[p2].sum() * KW / 1000 <= CAP:
                    out.append((p2, "②소유"))
                else:
                    pending.append(p2)
        stats["소유분할"] += len(pending)
        # ③ 콤팩트: 주축 누적 용량 절단 (결정론)
        for p2 in pending:
            pts = REPS[p2]
            c = pts - pts.mean(0)
            ax = np.linalg.svd(c, full_matrices=False)[2][0]
            order = p2[np.argsort(c @ ax)]
            smw = AREA[order].sum() * KW / 1000
            k = int(np.ceil(smw / CAP))
            cum = np.cumsum(AREA[order] * KW / 1000)
            cuts = np.searchsorted(cum, np.linspace(0, smw, k + 1)[1:-1])
            prev = 0
            for cut in list(cuts) + [len(order)]:
                if cut > prev:
                    out.append((order[prev:cut], "③콤팩트"))
                    prev = cut
            stats["콤팩트"] += k
    return out, stats


def seg_metrics(ix):
    a = AREA[ix]
    own = OWN[ix]
    known = own != "미확인"
    indiv = float(a[own == "개인"].sum() / a[known].sum()) if a[known].sum() else None
    unk = float(a[~known].sum() / a.sum()) if a.sum() else 0
    return a.sum() * KW / 1000, indiv, unk


def rings_of(ix):
    u = unary_union([GEOMS[i].buffer(12.5) for i in ix]).buffer(-9.5).simplify(5)
    u = shp_transform(TRI, u)
    polys = u.geoms if u.geom_type == "MultiPolygon" else [u]
    return [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in polys]


# ── T2② + T3: 접합안별 산출 ──
ALL = np.arange(N)
by_join = {}
t3 = {}
for jm in JOINS:
    t0 = time.time()
    blocks = decompose(ALL, jm)
    mws = np.array([AREA[ix].sum() * KW / 1000 for ix in blocks])
    big3 = [ix for ix in blocks if AREA[ix].sum() * KW / 1000 >= MIN_MW]
    # 최대 블록 3단 분할 통계 (T3)
    imax = int(np.argmax([AREA[ix].sum() for ix in blocks]))
    segs_max, st = split3(blocks[imax], jm)
    seg_mws = sorted((AREA[sx].sum() * KW / 1000 for sx, _ in segs_max), reverse=True)
    t3[jm] = {"최대블록MW": round(st["입력MW"], 1),
              "리분할대상": st["리분할"], "소유분할잔여": st["소유분할"], "콤팩트절단": st["콤팩트"],
              "세그먼트수": len(segs_max),
              "세그MW분포": [round(x, 1) for x in seg_mws[:12]],
              "3MW미만탈락": sum(1 for x in seg_mws if x < MIN_MW)}
    # 전체 세그먼트 (지도용)
    records = []
    for bi, ix in enumerate(big3):
        for si, (seg, how) in enumerate(split3(ix, jm)[0]):
            mw, indiv, unk = seg_metrics(seg)
            if mw < MIN_MW:
                continue
            records.append({"bid": f"{bi}-{si}", "mw": round(mw, 2), "n": int(len(seg)),
                            "indiv": round(indiv, 4) if indiv is not None else None,
                            "unk": round(unk, 4), "how": how, "poly": rings_of(seg)})
    tot = sum(r["mw"] for r in records)
    by_join[jm] = {"blocks_total": len(blocks), "seg_n": len(records),
                   "seg_mw": round(tot), "max_block_mw": round(mws.max()),
                   "records": records}
    print(f"  접합 {jm}m: 블록 {len(blocks):,} / 등재 세그 {len(records)} · {tot:,.0f}MW "
          f"/ 최대 블록 {mws.max():,.0f}MW ({time.time()-t0:.0f}s)", flush=True)

print("\n=== T3: 최대 블록 3단 분할 (접합안별) ===")
for jm in [15, 25, 35]:
    v = t3[jm]
    print(f"  {jm}m: 최대 {v['최대블록MW']}MW → ①리분할 대상 {v['리분할대상']} "
          f"②소유분할 잔여 {v['소유분할잔여']} ③콤팩트 {v['콤팩트절단']}회 "
          f"→ {v['세그먼트수']}세그 (상위: {v['세그MW분포'][:6]}, <3MW 탈락 {v['3MW미만탈락']})")

json.dump({"sgg": SGG, "hist": {"edges": [int(e) for e in edges[:-1]], "counts": hist.tolist()},
           "gap_stats": {"touch_pct": round(float((gaps <= 0.5).mean() * 100), 1),
                         "median_pos": round(float(np.median(pos)), 1),
                         "p75": round(float(np.percentile(pos, 75)), 1),
                         "p90": round(float(np.percentile(pos, 90)), 1)},
           "by_join": by_join, "t3": t3},
          open(os.path.join(PROTO, "join_study.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("\n저장: block_proto/join_study.json")
