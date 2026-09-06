# -*- coding: utf-8 -*-
"""18_block_production.py — E2 본 산출: 블록 방법론 (2026-07-16 잠금)
=================================================================
후보 = 적격 필지 연접 블록(접합 25m 확정) → ≥3MW 등재 → 50MW 초과 3단 분할
(①법정리 ②소유 경계 ③콤팩트) + 파편 보완(<3MW 조각은 최근접 형제 재병합
/ '잔여 구획', 파편 등재 금지). t 스윕 = 세그 필터 집계 (재클러스터링 불필요).

출력: pipeline_out/blocks/{sgg}_{scn}.json    (세그 레코드+summary, 지도 겸용)
      pipeline_out/blocks/{sgg}_{scn}_members.json
      pipeline_out/blocks_sweep_summary.json  (시군 판정: b_mw by t, 문턱, 상태)
사용: python 18_block_production.py [sgg콤마|all] [S0|S3|both]
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
BL = os.path.join(OUT, "blocks")
os.makedirs(BL, exist_ok=True)
KW, CAP, MIN_MW, JOIN, UNK_TH = 0.045, 50.0, 3.0, 25.0, 0.20
TS = [0.10, 0.20, 0.30, 0.40, 0.50]
TRI = Transformer.from_crs(5186, 4326, always_xy=True).transform
A_CODES = ["44270", "44180", "44200", "44130", "44210", "44800", "41590",
           "41220", "41460", "41270", "41390", "41500", "41480", "41570",
           "44810"]  # 생활권 병합 표시코드: 천안=44130(2구)·용인=41460(3구)·안산=41270(2구) — 2026-07-22 일관 적용

_b = pd.read_csv(os.path.join(OUT, "bjd_codes_20250805.csv"), encoding="cp949", dtype=str)
_b = _b[_b["폐지여부"] == "존재"]
RI_NM = _b.set_index("법정동코드")["법정동명"]


def ri_name(code10):
    nm = RI_NM.get(code10, RI_NM.get(code10[:8] + "00", code10))
    return " ".join(str(nm).split()[-2:]) if pd.notna(nm) else code10


# 표시코드 = [구성 물리코드] — 생활권 단위 병합 규칙, 천안·용인·안산 일관 적용 (재분리 금지)
#   2026-07-16 천안 확정 → 2026-07-22 용인·안산 확장 (코드↔시군 병합 비일관성 제거).
#   병합 = 단순 가산이 아니라 '재블록화': 구성 구의 필지 집합 전체에 25m 연접·50MW 3단
#   분할을 재실행하므로 구 경계를 넘는 연접이 하나의 블록이 될 수 있음.
MERGE = {"44130": ["44131", "44133"],
         "41460": ["41461", "41463", "41465"],   # 용인시 = 처인+기흥+수지
         "41270": ["41271", "41273"],            # 안산시 = 상록+단원
         "47110": ["47111", "47113"],            # 포항시 = 남구+북구 (B 일반구 분리 해소, 2026-07-22)
         "31000": ["31110", "31140", "31170", "31200", "31710"]}  # 울산광역시 = 중·남·동·북구+울주군 (2026-07-23 사용자 결정, B 광역 거점 단위)


class Engine:
    def __init__(self, sgg):
        self.sgg = sgg
        parts = MERGE.get(sgg, [sgg])  # 병합 코드는 구성 물리코드 전부 읽어 구계 넘는 블록도 병합
        pfs, gs = [], []
        for p in parts:
            pf = pd.read_parquet(os.path.join(OUT, "parcels_final", f"{p}.parquet"),
                                 columns=["pnu", "s0_eligible", "s1_eligible", "s2_eligible", "area_m2",
                                          "owner_class", "dong_code"])
            pfs.append(pf)
            g = gpd.read_file(os.path.join(BASE, "Base", "Base", f"{p}.gpkg"))
            pc = next(c for c in g.columns if c.lower() == "pnu")
            g = g.rename(columns={pc: "pnu"})[["pnu", "geometry"]]
            g["pnu"] = g["pnu"].astype(str).str.zfill(19)
            g = g.to_crs(epsg=5186)  # 구성 코드별 원천 CRS 상이(WGS84/KGD2002 혼재) — concat 전 통일 (2026-07-22 병합 확장 시 발견)
            sp = os.path.join(OUT, "nojimok_repair", "supplement", f"{p}_geom.gpkg")
            if os.path.exists(sp):
                s = gpd.read_file(sp)[["pnu", "geometry"]].to_crs(epsg=5186)
                s["pnu"] = s["pnu"].astype(str).str.zfill(19)
                g = pd.concat([g[~g["pnu"].isin(set(s["pnu"]))], s], ignore_index=True)
            gs.append(g)
        pf = pd.concat(pfs, ignore_index=True).set_index("pnu")
        g = pd.concat(gs, ignore_index=True).set_crs(epsg=5186, allow_override=True)
        g = g[g["pnu"].isin(set(pf.index))]
        self.g = g.drop_duplicates("pnu").reset_index(drop=True)
        att = pf.reindex(self.g["pnu"])
        self.AREA = att["area_m2"].values
        self.OWN = att["owner_class"].values
        self.RI = att["dong_code"].astype(str).str.zfill(10).values
        self.EL = {"S0": att["s0_eligible"].values == 1, "S1": att["s1_eligible"].values == 1, "S2": att["s2_eligible"].values == 1}
        self.GEOMS = self.g.geometry.values
        self.REPS = np.array([[p.x, p.y] for p in self.g.geometry.representative_point()])
        self.PNU = self.g["pnu"].values

    def decompose(self, idx):
        u = unary_union([self.GEOMS[i].buffer(JOIN / 2) for i in idx])
        bl = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
        tr = STRtree(bl)
        asn = np.full(len(idx), -1)
        for k, i in enumerate(idx):
            rp = self.GEOMS[i].representative_point()
            for j in tr.query(rp):
                if bl[j].intersects(rp):
                    asn[k] = j
                    break
        return [idx[asn == j] for j in range(len(bl)) if (asn == j).any()]

    def _axis_cut(self, p2):
        pts = self.REPS[p2]
        c = pts - pts.mean(0)
        ax = np.linalg.svd(c, full_matrices=False)[2][0]
        order = p2[np.argsort(c @ ax)]
        smw = self.AREA[order].sum() * KW / 1000
        k = int(np.ceil(smw / CAP))
        cum = np.cumsum(self.AREA[order] * KW / 1000)
        cuts = np.searchsorted(cum, np.linspace(0, smw, k + 1)[1:-1])
        segs, prev = [], 0
        for cut in list(cuts) + [len(order)]:
            if cut > prev:
                segs.append(order[prev:cut])
                prev = cut
        return segs

    def split3(self, ix):
        """승인 규칙 + 파편 보완: <3MW 소유 조각은 최근접 형제 재병합 / 잔여 구획."""
        if self.AREA[ix].sum() * KW / 1000 <= CAP:
            return [(ix, "무분할")]
        out = []
        for ri in np.unique(self.RI[ix]):
            p1 = ix[self.RI[ix] == ri]
            if self.AREA[p1].sum() * KW / 1000 <= CAP:
                out.append((p1, "①리"))
                continue
            subs, frags = [], []
            for grp in np.unique(self.OWN[p1]):
                for p2 in self.decompose(p1[self.OWN[p1] == grp]):
                    (subs if self.AREA[p2].sum() * KW / 1000 >= MIN_MW else frags).append(p2)
            merged_tag = "②소유"
            if frags:
                if subs:  # 최근접 형제에 재병합
                    cents = np.array([self.REPS[s].mean(0) for s in subs])
                    add = [[] for _ in subs]
                    for f in frags:
                        d = ((cents - self.REPS[f].mean(0)) ** 2).sum(1)
                        add[int(np.argmin(d))].append(f)
                    subs = [np.concatenate([s] + a) if a else s for s, a in zip(subs, add)]
                    merged_tag = "②소유+병합"
                else:  # 형제 없음 → 잔여 구획
                    resid = np.concatenate(frags)
                    if self.AREA[resid].sum() * KW / 1000 >= MIN_MW:
                        subs = [resid]
                        merged_tag = "잔여구획"
                    # 잔여도 <3MW → 미등재 (파편 등재 금지)
            for s in subs:
                if self.AREA[s].sum() * KW / 1000 <= CAP:
                    out.append((s, merged_tag))
                else:
                    out.extend((c, "③콤팩트") for c in self._axis_cut(s))
        return out

    def rings(self, ix):
        u = unary_union([self.GEOMS[i].buffer(12.5) for i in ix]).buffer(-9.5).simplify(5)
        u = shp_transform(TRI, u)
        polys = u.geoms if u.geom_type == "MultiPolygon" else [u]
        return [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in polys]

    def run(self, scn):
        idx = np.where(self.EL[scn])[0]
        blocks = self.decompose(idx)
        records, members = [], {}
        for bi, bx in enumerate(blocks):
            if self.AREA[bx].sum() * KW / 1000 < MIN_MW:
                continue
            for si, (seg, how) in enumerate(self.split3(bx)):
                a = self.AREA[seg]
                mw = a.sum() * KW / 1000
                if mw < MIN_MW:
                    continue
                own = self.OWN[seg]
                known = own != "미확인"
                indiv = float(a[own == "개인"].sum() / a[known].sum()) if a[known].sum() else None
                unk = float(a[~known].sum() / a.sum())
                ri_areas = pd.Series(a).groupby(pd.Series(self.RI[seg])).sum()
                dom_ri = ri_areas.idxmax()
                bid = f"{bi}-{si}"
                records.append({"bid": bid, "block": bi, "mw": round(mw, 2),
                                "n": int(len(seg)), "ha": round(a.sum() / 10000, 1),
                                "indiv": round(indiv, 4) if indiv is not None else None,
                                "unk": round(unk, 4), "how": how,
                                "loc": ri_name(dom_ri), "ri": dom_ri, "sub": False,
                                "poly": self.rings(seg)})
                members[bid] = self.PNU[seg].tolist()
                # 하위구획 보완 (2026-07-15 채택): 세그가 t에서 탈락할 때를 위한
                # 비개인(공공·법인 확정) 연접 ≥3MW 구획 — t 무관 사전 산출
                if indiv is not None and indiv > 0.10:  # indiv≤0.10이면 어떤 t에도 통과
                    nonp = seg[(own != "개인") & (own != "미확인")]
                    if len(nonp):
                        for k, sb in enumerate(self.decompose(nonp)):
                            smw = self.AREA[sb].sum() * KW / 1000
                            if smw < MIN_MW:
                                continue
                            sa = self.AREA[sb]
                            sbid = f"{bid}s{k}"
                            records.append({"bid": sbid, "block": bi, "parent": bid,
                                            "mw": round(smw, 2), "n": int(len(sb)),
                                            "ha": round(sa.sum() / 10000, 1),
                                            "indiv": 0.0, "unk": 0.0, "how": "하위구획",
                                            "loc": ri_name(pd.Series(sa).groupby(
                                                pd.Series(self.RI[sb])).sum().idxmax()),
                                            "sub": True, "poly": self.rings(sb)})
                            members[sbid] = self.PNU[sb].tolist()
        tot = sum(r["mw"] for r in records if not r["sub"])  # 총량은 모세그만
        by_t = {}
        parents = [r for r in records if not r["sub"]]
        subs_by_parent = {}
        for r in records:
            if r["sub"]:
                subs_by_parent.setdefault(r["parent"], []).append(r)
        for t in TS:
            b_n = 0
            b_mw = 0.0
            for r in parents:
                if r["unk"] <= UNK_TH and r["indiv"] is not None and r["indiv"] <= t:
                    b_n += 1
                    b_mw += r["mw"]  # 모세그 통과 → 하위구획 미사용 (이중 계상 금지)
                else:
                    for s in subs_by_parent.get(r["bid"], []):  # 탈락 모의 하위구획만
                        b_n += 1
                        b_mw += s["mw"]
            by_t[f"{t:.2f}"] = {"b_n": b_n, "b_mw": round(b_mw, 1)}
        summary = {"sgg": self.sgg, "scenario": scn, "join_m": JOIN,
                   "seg_n": len(records), "seg_mw": round(tot, 1),
                   "by_t": by_t,
                   "threshold_t_50": next((k for k in sorted(by_t) if by_t[k]["b_mw"] >= 50), "미달"),
                   "threshold_t_100": next((k for k in sorted(by_t) if by_t[k]["b_mw"] >= 100), "미달"),
                   "b_mw_t30": by_t["0.30"]["b_mw"],
                   "status_t30": ("유력" if by_t["0.30"]["b_mw"] >= 100 else
                                  "지정 가능" if by_t["0.30"]["b_mw"] >= 50 else "요건 미달")}
        json.dump({"summary": summary,
                   "records": records},
                  open(os.path.join(BL, f"{self.sgg}_{scn}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        json.dump(members, open(os.path.join(BL, f"{self.sgg}_{scn}_members.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        return summary


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    scns = ["S0", "S1", "S2"] if len(sys.argv) < 3 or sys.argv[2] == "both" else [sys.argv[2]]
    sggs = A_CODES if arg == "all" else arg.split(",")
    sweep = {}
    for sgg in sggs:
        t0 = time.time()
        try:
            eng = Engine(sgg)
            sweep[sgg] = {}
            for scn in scns:
                s = eng.run(scn)
                sweep[sgg][scn] = s
                print(f"  {sgg} {scn}: 세그 {s['seg_n']} · {s['seg_mw']:,}MW / "
                      f"b(t0.30) {s['b_mw_t30']:,}MW [{s['status_t30']}] "
                      f"t50={s['threshold_t_50']} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            import traceback
            print(f"[ERR] {sgg}: {e}", flush=True)
            traceback.print_exc()
    out = os.path.join(OUT, "blocks_sweep_summary.json")
    if os.path.exists(out):
        old = json.load(open(out, encoding="utf-8"))
        for sgg, scns in sweep.items():  # 시나리오 단위 병합 (sgg 통째 교체 금지 — S0/S3 보존)
            old.setdefault(sgg, {}).update(scns)
        sweep = old
    json.dump(sweep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("blocks_sweep_summary.json 갱신")
