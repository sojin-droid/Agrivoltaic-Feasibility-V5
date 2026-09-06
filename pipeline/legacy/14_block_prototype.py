# -*- coding: utf-8 -*-
"""14_block_prototype.py — 방법론 피벗 프로토타입 (당진): 후보지구 = 연접 블록
=================================================================
승인 조건(2026-07-15): 전면 교체는 프로토타입 검수 후. 필수 산출 —
 1) 신구 t 스윕 비교 (구 b_mw vs 신: 블록 indiv≤t ∧ 미확인≤20% 합산)
 2) 50MW 초과 블록 분할: 1차 법정리 경계(행정·수용성 근거) →
    2차 주축(principal axis) 누적 용량 분할(50MW=기확정 cap, 결정론적).
    693MW 최대 블록 분할 예시 출력
 3) 접합 민감도 15/25/35m — 신 방법론 기준(블록 수·≥3MW 수·MW·최대)
 4) 블록별 개인소유·미확인 비율 (면적가중, 15개 시군 원장과 동일 정의)
출력: pipeline_out/block_proto/44270_blocks.json (지도용) + 표 stdout
"""
import os, sys, io, json
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
os.makedirs(PROTO, exist_ok=True)
SGG = "44270"
KW = 0.045
CAP_MW = 50.0
MIN_MW = 3.0
UNK_TH = 0.20
TRI = Transformer.from_crs(5186, 4326, always_xy=True).transform

# ── 데이터 ──
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
print(f"당진 S3 적격 {len(g):,}필지", flush=True)
AREA = pf["area_m2"].reindex(g["pnu"]).values
OWN = pf["owner_class"].reindex(g["pnu"]).values
RI = pf["dong_code"].reindex(g["pnu"]).astype(str).str.zfill(10).values
REPS = np.array([[p.x, p.y] for p in g.geometry.representative_point()])


def decompose(join_m):
    """연접 블록 분해 → 필지 인덱스 리스트 목록"""
    u = unary_union(g.geometry.buffer(join_m / 2).values)
    bl = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    tree = STRtree(bl)
    assign = np.full(len(g), -1)
    for k, geom in enumerate(g.geometry):
        rp = geom.representative_point()
        for i in tree.query(rp):
            if bl[i].intersects(rp):
                assign[k] = i
                break
    return [np.where(assign == i)[0] for i in range(len(bl)) if (assign == i).any()]


# ── 3) 접합 민감도 (신 방법론 기준) ──
print("\n=== 접합 민감도 (신 방법론: 소유 무관 블록) ===")
sens_rows = []
for jm in [15, 25, 35]:
    blocks = decompose(jm)
    mws = np.array([AREA[ix].sum() * KW / 1000 for ix in blocks])
    q = mws[mws >= MIN_MW]
    sens_rows.append({"접합m": jm, "전체블록": len(blocks), "≥3MW블록": len(q),
                      "≥3MW합MW": round(q.sum()), "최대MW": round(mws.max())})
    print(f"  {jm}m: 전체 {len(blocks):,} / ≥3MW {len(q)}개 · {q.sum():,.0f}MW / 최대 {mws.max():,.0f}MW", flush=True)
pd.DataFrame(sens_rows).to_csv(os.path.join(PROTO, "join_sensitivity.csv"), index=False, encoding="utf-8-sig")

# ── 본 분해 (잠정 25m) ──
blocks = decompose(25)


def block_metrics(ix):
    a = AREA[ix]
    own = OWN[ix]
    known = own != "미확인"
    indiv = a[(own == "개인")].sum() / a[known].sum() if a[known].sum() else None
    unk = a[~known].sum() / a.sum() if a.sum() else 0
    return a.sum() * KW / 1000, indiv, unk


# ── 2) 50MW 초과 분할: ①법정리 ②주축 누적용량 ──
def split_block(ix):
    """반환: 세그먼트 목록 [(필지idx배열, 분할경로 문자열)]"""
    mw = AREA[ix].sum() * KW / 1000
    if mw <= CAP_MW:
        return [(ix, "무분할")]
    segs = []
    for ri in np.unique(RI[ix]):
        sub = ix[RI[ix] == ri]
        smw = AREA[sub].sum() * KW / 1000
        if smw <= CAP_MW:
            segs.append((sub, f"리분할({ri[8:]})"))
        else:  # 주축 누적 용량 분할 (결정론적: PCA 1축 정렬 → 50MW 단위 절단)
            pts = REPS[sub]
            c = pts - pts.mean(0)
            ax = np.linalg.svd(c, full_matrices=False)[2][0]
            order = sub[np.argsort(c @ ax)]
            k = int(np.ceil(smw / CAP_MW))
            target = smw / k
            cur, acc = [], 0.0
            for p in order:
                cur.append(p)
                acc += AREA[p] * KW / 1000
                if acc >= target and len(segs) is not None and k > 1:
                    segs.append((np.array(cur), f"리({ri[8:]})+주축"))
                    cur, acc = [], 0.0
                    k -= 1
                    remaining = AREA[np.setdiff1d(order, np.concatenate([s[0] for s in segs if s[1].startswith(f'리({ri[8:]})')]) if segs else order)].sum() * KW / 1000
                    target = remaining / k if k else acc
            if cur:
                segs.append((np.array(cur), f"리({ri[8:]})+주축"))
    return segs


# 단순화: 위 주축 분할 재구현 (명료 버전)
def split_block(ix):
    mw = AREA[ix].sum() * KW / 1000
    if mw <= CAP_MW:
        return [(ix, "무분할")]
    segs = []
    for ri in np.unique(RI[ix]):
        sub = ix[RI[ix] == ri]
        smw = AREA[sub].sum() * KW / 1000
        if smw <= CAP_MW:
            segs.append((sub, "리분할"))
            continue
        pts = REPS[sub]
        c = pts - pts.mean(0)
        ax = np.linalg.svd(c, full_matrices=False)[2][0]
        order = sub[np.argsort(c @ ax)]
        k = int(np.ceil(smw / CAP_MW))
        bounds = np.linspace(0, smw, k + 1)[1:-1]
        cum = np.cumsum(AREA[order] * KW / 1000)
        cuts = np.searchsorted(cum, bounds)
        prev = 0
        for cut in list(cuts) + [len(order)]:
            if cut > prev:
                segs.append((order[prev:cut], "리+주축분할"))
                prev = cut
    return segs


# ── 등재 세그먼트 구축 ──
records = []
max_block_i = int(np.argmax([AREA[ix].sum() for ix in blocks]))
for bi, ix in enumerate(blocks):
    mw = AREA[ix].sum() * KW / 1000
    if mw < MIN_MW:
        continue
    for si, (seg, how) in enumerate(split_block(ix)):
        smw, indiv, unk = block_metrics(seg)
        if smw < MIN_MW:
            continue  # 분할 잔여 조각이 3MW 미만이면 미등재
        ris = sorted(set(RI[seg]))
        records.append({"bid": f"{bi}-{si}", "block": bi, "mw": round(smw, 2),
                        "n": len(seg), "indiv": round(indiv, 4) if indiv is not None else None,
                        "unk": round(unk, 4), "how": how,
                        "ri": [r[:10] for r in ris], "ix": seg.tolist()})
print(f"\n=== 등재 세그먼트(≥3MW, 분할 후): {len(records)}개 · {sum(r['mw'] for r in records):,.0f}MW ===")

# 693MW 최대 블록 분할 예시
mx = [r for r in records if r["block"] == max_block_i]
print(f"최대 블록(#{max_block_i}, {AREA[blocks[max_block_i]].sum()*KW/1000:,.0f}MW) 분할 예시: "
      f"{len(mx)}개 세그먼트 — " + ", ".join(f"{r['mw']:.0f}MW({r['how']})" for r in mx[:10])
      + (" …" if len(mx) > 10 else ""), flush=True)

# ── 1) 신구 t 스윕 비교 ──
old = json.load(open(os.path.join(OUT, "ownership_sweep_summary.json"), encoding="utf-8"))[SGG]["by_t"]
print("\n=== 신구 t 스윕 비교 (당진, MW) ===")
print("t     구(지구 exec, 공식∧미확인≤20%)   신(블록 indiv≤t ∧ 미확인≤20%)")
comp = []
for t in [0.10, 0.20, 0.30, 0.40, 0.50]:
    new = sum(r["mw"] for r in records
              if r["indiv"] is not None and r["indiv"] <= t and r["unk"] <= UNK_TH)
    o = old[f"0.{int(t*100)}"]["b_mw"]
    comp.append({"t": t, "구": o, "신": round(new, 1), "비율": round(new / o, 2) if o else None})
    print(f"0.{int(t*100)}   {o:>10,.0f}                     {new:>10,.0f}  ({new/o*100 if o else 0:.0f}%)")
pd.DataFrame(comp).to_csv(os.path.join(PROTO, "t_sweep_comparison.csv"), index=False, encoding="utf-8-sig")

# ── 지도 데이터 (폴리곤 포함) ──
geo = []
for r in records:
    seg_geoms = g.geometry.values[np.array(r["ix"])]
    u = unary_union([x.buffer(12.5) for x in seg_geoms]).buffer(-9.5).simplify(5)
    u = shp_transform(TRI, u)
    polys = u.geoms if u.geom_type == "MultiPolygon" else [u]
    rings = [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in polys]
    geo.append({k: r[k] for k in ("bid", "block", "mw", "n", "indiv", "unk", "how")} | {"poly": rings})
json.dump({"sgg": SGG, "join_m": 25, "records": geo,
           "sens": sens_rows, "comp": comp},
          open(os.path.join(PROTO, "44270_blocks.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"\n지도 데이터 저장: block_proto/44270_blocks.json ({len(geo)} 세그먼트)")
