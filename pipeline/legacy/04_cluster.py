# -*- coding: utf-8 -*-
"""04_cluster.py — 용량제약 영역성장 클러스터링 + 적응형 병합 패스 (Phase 3)
=================================================================
구 build_candidate_clusters.py 대비 변경:
  - 입력: Supabase parcels 테이블 (--local 시 pipeline_out/parcels_final 파케이)
  - 적격: s0_eligible / s2_eligible (Phase 1 확정 필터 체계)
  - 시드: "개인소유 비율이 낮은 필지" 우선 (indiv_ratio 오름차순, 결측 배제)
  - t(개인소유 비율 상한): 성장 제약으로 사전 반영 (위반 필지 스킵)
  - 병합 패스(선택): 병합 거리는 임의 상수가 아니라 각 시군 필지 간격
    분포에서 도출 — r_local = 클러스터 내부 필지 NN 간격의 P95
    (지구 간 간격이 내부 간격 상위 5% 이내면 통계적으로 구별 불가능 → 병합).
      과대 병합 방지: ① 병합 후 ≤ 50MW
                      ② 병합 후 지름 ≤ max(구성 지구 지름) + 2×r_local
                        (병합 기하의 필연 상한 — 자유상수 없음)

사용:
  python 04_cluster.py --sgg 44270 --scenario S3 --t 0.30 [--merge]
"""
import os, sys, io, json, time, heapq, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import defaultdict
import numpy as np
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
ENV_PATH = os.path.join(BASE, "pipeline", ".env")

EPS_M = 200.0
MIN_PTS = 3
KW_PER_M2 = 0.045
CAP_KW = 50.0 * 1000
CAP_FACTOR = 8760 * 0.15
UNIT_M2 = 1000.0


def load_env():
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_parcels(sgg, scenario, local=False):
    col = "s0_eligible" if scenario == "S0" else "s2_eligible"
    cols = ["pnu", "lon", "lat", "area_m2", "indiv_ratio", "owner_class", "emd_code"]
    if local:
        df = pd.read_parquet(os.path.join(BASE, "pipeline_out", "parcels_final",
                                          f"{sgg}.parquet"))
        return df[df[col] == 1][cols].reset_index(drop=True)
    import psycopg2
    load_env()
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    df = pd.read_sql(
        f"""SELECT pnu, ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   area_m2::float8 AS area_m2, indiv_ratio, owner_class, emd_code
            FROM parcels WHERE sgg_code = %s AND {col}""",
        conn, params=(sgg,))
    conn.close()
    return df


def grow_blobs(df, t_cap=None):
    """DBSCAN 연결성분 → (50MW cap + t 제약) 영역성장. blob = 필지 인덱스 리스트."""
    from sklearn.cluster import DBSCAN
    from scipy.spatial import cKDTree
    from pyproj import Transformer

    tr = Transformer.from_crs(4326, 5186, always_xy=True)
    x, y = tr.transform(df["lon"].values, df["lat"].values)
    pts = np.column_stack([x, y])
    area = df["area_m2"].values
    indiv = df["indiv_ratio"].values
    is_priv = (df["owner_class"] == "개인").values
    pnu = df["pnu"].values

    labels = DBSCAN(eps=EPS_M, min_samples=MIN_PTS).fit_predict(pts)
    comps = defaultdict(list)
    for i, lab in enumerate(labels):
        if lab >= 0:
            comps[lab].append(i)
    n_noise = int((labels < 0).sum())

    tree = cKDTree(pts)
    neigh = tree.query_ball_point(pts, r=EPS_M, workers=-1)

    blobs, leftover = [], []
    n_seeds = 0
    for comp in comps.values():
        comp_set = set(comp)
        assigned = set()
        seed_order = sorted((i for i in comp if not np.isnan(indiv[i])),
                            key=lambda i: (indiv[i], pnu[i]))
        for seed in seed_order:
            if seed in assigned:
                continue
            n_seeds += 1
            blob = [seed]
            assigned.add(seed)
            cum_kw = area[seed] * KW_PER_M2
            ind_area = area[seed] if is_priv[seed] else 0.0
            tot_area = area[seed]
            sx, sy = pts[seed]
            heap, seen = [], set()

            def push(i):
                for j in neigh[i]:
                    if j in comp_set and j not in assigned and j not in seen:
                        seen.add(j)
                        d2 = (pts[j][0]-sx)**2 + (pts[j][1]-sy)**2
                        heapq.heappush(heap, (d2, pnu[j], j))

            push(seed)
            while heap:
                _, _, j = heapq.heappop(heap)
                if j in assigned:
                    continue
                cost = area[j] * KW_PER_M2
                if cum_kw + cost > CAP_KW:
                    break
                if t_cap is not None and is_priv[j]:
                    if (ind_area + area[j]) / (tot_area + area[j]) > t_cap:
                        continue
                assigned.add(j)
                blob.append(j)
                cum_kw += cost
                tot_area += area[j]
                if is_priv[j]:
                    ind_area += area[j]
                push(j)

            if len(blob) < MIN_PTS:
                for i in blob:
                    assigned.discard(i)
                n_seeds -= 1
                continue
            blobs.append(blob)
        leftover.extend(i for i in comp if i not in assigned)
    leftover.extend(i for i in range(len(df)) if labels[i] < 0)
    return blobs, leftover, n_noise, n_seeds, pts


def compute_gap_stats(pts, blobs):
    """클러스터 내부 필지 최근접 이웃 거리의 (중앙값, P95). 시군 단위 스칼라.
    병합 반경 r = P95 — 지구 간 간격이 내부 간격 분포의 상위 5% 이내면
    내부 간격과 통계적으로 구별 불가능하다는 규칙 (2026-07-13 확정)."""
    from scipy.spatial import cKDTree
    nn = []
    for blob in blobs:
        if len(blob) < 2:
            continue
        sub = pts[blob]
        t = cKDTree(sub)
        d, _ = t.query(sub, k=2)
        nn.extend(d[:, 1].tolist())
    if not nn:
        return float("nan"), float("nan")
    return float(np.median(nn)), float(np.percentile(nn, 95))


def _hull_idx(sub_pts):
    """projected 좌표 convex hull 꼭짓점 인덱스 (monotone chain, 소수 점 대응)."""
    order = sorted(range(len(sub_pts)), key=lambda i: (sub_pts[i][0], sub_pts[i][1]))
    if len(order) < 3:
        return order
    def cross(o, a, b):
        return ((sub_pts[a][0]-sub_pts[o][0])*(sub_pts[b][1]-sub_pts[o][1])
                - (sub_pts[a][1]-sub_pts[o][1])*(sub_pts[b][0]-sub_pts[o][0]))
    lower, upper = [], []
    for i in order:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], i) <= 0:
            lower.pop()
        lower.append(i)
    for i in reversed(order):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], i) <= 0:
            upper.pop()
        upper.append(i)
    return lower[:-1] + upper[:-1]


def _diameter(hull_xy):
    if len(hull_xy) < 2:
        return 0.0
    arr = np.asarray(hull_xy)
    d2 = ((arr[:, None, :] - arr[None, :, :]) ** 2).sum(-1)
    return float(np.sqrt(d2.max()))


def merge_pass(blobs, pts, area, r):
    """적응형 병합: 간격 ≤ r(=내부 간격 P95) 지구쌍을 가까운 순으로 병합.
    거부: ① 합계 > 50MW ② 병합 후 지름 > max(구성 지름) + 2r
    (병합 기하가 허용하는 필연 상한 — 자유상수 없음, 연쇄 확장 자동 차단)
    ③ 브리지가 하천·철도 지목 필지를 횡단 (2026-07-15 확정 — 도로·구거는 허용)."""
    from scipy.spatial import cKDTree

    label = {}
    for ci, blob in enumerate(blobs):
        for i in blob:
            label[i] = ci
    assigned_idx = np.array(sorted(label.keys()))
    tree = cKDTree(pts[assigned_idx])
    pairs = tree.query_pairs(r=r, output_type="ndarray")

    gap, seg = {}, {}
    for a, b in pairs:
        ia, ib = assigned_idx[a], assigned_idx[b]
        ca, cb = label[ia], label[ib]
        if ca == cb:
            continue
        key = (min(ca, cb), max(ca, cb))
        d = float(np.hypot(*(pts[ia] - pts[ib])))
        if d < gap.get(key, np.inf):
            gap[key] = d
            seg[key] = (tuple(pts[ia]), tuple(pts[ib]))

    parent = list(range(len(blobs)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    kw = [sum(area[i] for i in b) * KW_PER_M2 for b in blobs]
    hull_pts, diam = [], []
    for b in blobs:
        sub = [tuple(pts[i]) for i in b]
        h = [sub[i] for i in _hull_idx(sub)]
        hull_pts.append(h)
        diam.append(_diameter(h))

    from cross_check import bridge_crossing  # 하천·철도 횡단 판정 (캐시)
    n_merge = rej_cap = rej_diam = rej_cross = n_cross_err = 0
    for (ca, cb), d in sorted(gap.items(), key=lambda x: x[1]):
        ra, rb = find(ca), find(cb)
        if ra == rb:
            continue
        if kw[ra] + kw[rb] > CAP_KW:
            rej_cap += 1
            continue
        comb = hull_pts[ra] + hull_pts[rb]
        comb_hull = [comb[i] for i in _hull_idx(comb)]
        comb_diam = _diameter(comb_hull)
        if comb_diam > max(diam[ra], diam[rb]) + 2 * r:
            rej_diam += 1
            continue
        if os.environ.get("NOCROSS_OFF") == "1":  # 비교 분석용 규칙 해제
            types = set()
        else:
            types = bridge_crossing(*seg[(min(ca, cb), max(ca, cb))])
        if types is None:
            n_cross_err += 1  # API 불능 시 종전 규칙으로 진행 (허용)
        elif types & {"하천", "철도"}:
            rej_cross += 1
            continue
        parent[rb] = ra
        kw[ra] += kw[rb]
        hull_pts[ra] = comb_hull
        diam[ra] = comb_diam
        n_merge += 1

    merged = defaultdict(list)
    for ci, blob in enumerate(blobs):
        merged[find(ci)].extend(blob)
    stats = {"r_m": round(r, 1), "rule": "P95+geom+nocross(하천·철도)",
             "n_pairs": len(gap), "n_merged": n_merge,
             "rejected_cap": rej_cap, "rejected_diam": rej_diam,
             "rejected_cross": rej_cross, "cross_check_err": n_cross_err}
    return list(merged.values()), stats


def blob_metrics(df, pts, blobs):
    area = df["area_m2"].values
    is_priv = (df["owner_class"] == "개인").values
    is_unknown = (df["owner_class"] == "미확인").values
    out = []
    for blob in sorted(blobs, key=lambda b: -area[b].sum()):
        a = float(area[blob].sum())
        ind_a = float(area[blob][is_priv[blob]].sum())
        unk_a = float(area[blob][is_unknown[blob]].sum())
        sub = [tuple(pts[i]) for i in blob]
        hull_i = _hull_idx(sub)
        diam = _diameter([sub[i] for i in hull_i])
        units = a / UNIT_M2
        mw = units * KW_PER_M2
        # tier: 대형 강조(large ≥10MW) / 공식 집계 대상(standard ≥3MW) / 탐색용(sub)
        tier = "large" if mw >= 10 else ("standard" if mw >= 3 else "sub")
        out.append({
            "cluster_id": len(out), "n": len(blob),
            "area_m2": round(a, 1), "units": round(units, 1),
            "mw": round(units * KW_PER_M2, 3), "tier": tier,
            "annual_gwh": round(a * KW_PER_M2 * CAP_FACTOR / 1e6, 3),
            "indiv_ratio": round(ind_a / a, 4) if a else 0.0,
            "unknown_owner_ratio": round(unk_a / a, 4) if a else 0.0,
            "diameter_m": round(diam, 1),
            "emds": sorted({df["emd_code"].iloc[i] for i in blob}),
            "hull": [[round(df["lon"].iloc[blob[i]], 6),
                      round(df["lat"].iloc[blob[i]], 6)] for i in hull_i],
            "members_idx": [int(i) for i in blob],
        })
    return out


def mw_bins(clusters):
    bins = {"<=1MW": 0, "1-10MW": 0, "10-30MW": 0, "30-50MW": 0}
    for c in clusters:
        mw = c["mw"]
        if mw <= 1: bins["<=1MW"] += 1
        elif mw <= 10: bins["1-10MW"] += 1
        elif mw <= 30: bins["10-30MW"] += 1
        else: bins["30-50MW"] += 1
    return bins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sgg", required=True)
    ap.add_argument("--scenario", choices=["S0", "S3"], required=True)
    ap.add_argument("--t", type=float, default=None)
    ap.add_argument("--merge", action="store_true",
                    help="병합 패스 실행 (r=내부 간격 P95, 자유상수 없음)")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--out", default=os.path.join(BASE, "pipeline_out", "clusters"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    t0 = time.time()
    df = load_parcels(args.sgg, args.scenario, local=args.local)
    print(f"[{args.sgg} {args.scenario} t={args.t} merge={args.merge}] "
          f"적격 {len(df):,} (소스={'local' if args.local else 'DB'})")

    blobs, leftover, n_noise, n_seeds, pts = grow_blobs(df, t_cap=args.t)
    d_median, d_p95 = compute_gap_stats(pts, blobs)
    r_local = min(d_p95, EPS_M * 0.99) if not np.isnan(d_p95) else float("nan")
    print(f"  내부간격 중앙값 {d_median:.1f}m / P95 {d_p95:.1f}m → r_local {r_local:.1f}m")

    merge_stats = None
    if args.merge and blobs and not np.isnan(r_local):
        area = df["area_m2"].values
        blobs, merge_stats = merge_pass(blobs, pts, area, r_local)
        print(f"  병합: {merge_stats['n_merged']}건 "
              f"(후보쌍 {merge_stats['n_pairs']}, 거부 cap {merge_stats['rejected_cap']}"
              f"/지름 {merge_stats['rejected_diam']}, r={merge_stats['r_m']}m)")

    clusters = blob_metrics(df, pts, blobs)
    tot_a = sum(c["area_m2"] for c in clusters)
    tot_units = sum(c["units"] for c in clusters)
    tot_mw = sum(c["mw"] for c in clusters)
    diams = [c["diameter_m"] for c in clusters]

    tag = args.scenario + (f"_t{int(args.t*100)}" if args.t is not None else "") \
        + ("_merged" if args.merge else "")
    print(f"  거점(시드) {n_seeds:,} / 후보지구 {len(clusters):,} / "
          f"{tot_a/10000:,.1f} ha / 설치단위 {tot_units:,.0f} / {tot_mw:,.1f} MW")
    print(f"  규모분포 {mw_bins(clusters)} / 지름 중앙값 {np.median(diams):,.0f}m·"
          f"최대 {max(diams):,.0f}m / 미편입 {len(leftover):,} / "
          f"실행 {time.time()-t0:.1f}s")

    light = [{k: v for k, v in c.items() if k != "members_idx"} for c in clusters]
    members = {c["cluster_id"]: df["pnu"].iloc[c["members_idx"]].tolist()
               for c in clusters}
    official = [c for c in clusters if c["mw"] >= 3.0]  # 공식 집계 기준 3MW (2026-07-14 확정)
    summary = {"sgg": args.sgg, "scenario": args.scenario, "t": args.t,
               "gap_median_m": round(d_median, 2), "gap_p95_m": round(d_p95, 2),
               "r_local_m": round(r_local, 2), "merge": merge_stats,
               "n_seeds": n_seeds, "n_clusters": len(clusters),
               "n_clusters_official": len(official),
               "mw_official": round(sum(c["mw"] for c in official), 2),
               "official_min_mw": 3.0,
               "area_m2": round(tot_a, 1), "units": round(tot_units, 1),
               "mw": round(tot_mw, 2), "n_leftover": len(leftover),
               "mw_bins": mw_bins(clusters),
               "diam_median_m": round(float(np.median(diams)), 1) if diams else 0,
               "diam_max_m": round(max(diams), 1) if diams else 0}
    with open(os.path.join(args.out, f"{args.sgg}_clusters_{tag}.json"), "w",
              encoding="utf-8") as f:
        json.dump({"summary": summary, "clusters": light}, f,
                  ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(args.out, f"{args.sgg}_members_{tag}.json"), "w",
              encoding="utf-8") as f:
        json.dump(members, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(args.out, f"{args.sgg}_unassigned_{tag}.json"), "w",
              encoding="utf-8") as f:
        json.dump(df["pnu"].iloc[leftover].tolist(), f,
                  ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
