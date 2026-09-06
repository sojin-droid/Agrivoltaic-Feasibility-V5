# -*- coding: utf-8 -*-
"""A choropleth 재구축 — 전 법정동 색칠 통일(B와 동일 기준).

a_boundary_dongs.json(V-World 전 법정동 338동, 화성 제외) + 기존 choropleth의 화성 10동
→ KEPCO 계통(dispersedGeneration.do, 무인증) 전 동 조회 → equal_split+계층캡 →
choropleth의 A 전량 교체(B 303동은 유지). summary.json A grid_pool_mw 재산출.
"""
import io, os, sys, json, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EP = "https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do"
ROOT = r"C:\Users\user\새 폴더"
# ★주의 (2026-07-21 K36): a_boundary_dongs.json은 338동·15개 시군 프리픽스만 수록 —
#   화성(41590)·용인기흥(41463)·용인수지(41465)·안산단원(41273) 부재. 이 목록을 보완하기 전에
#   본 스크립트를 재실행하면 정본 site_v2\data\grid_choropleth.json(651동)이 축소본으로 덮인다.
ABND = os.path.join(ROOT, "pipeline_out", "a_boundary_dongs.json")
CHORO = os.path.join(ROOT, "site_v2", "data", "grid_choropleth.json")  # 2026-07-21 정정(K8): 정본 site_v2
SUMM = os.path.join(ROOT, "site_v2", "data", "summary.json")
CACHE = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-----\c890d164-6976-4299-b22a-aec933f33bbb\scratchpad\kepco_a_raw"
os.makedirs(CACHE, exist_ok=True)
B_PREF = {"41463","41465","41273","28200","46230","46130","47111","47113","47190","31110","31140","31170","31200","31710"}


def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None


def call_api(metro, city, dong):
    p = {"metroCd": metro, "cityCd": city, "addrLidong": dong, "apiKey": "", "returnType": "json"}
    for att in range(4):
        req = urllib.request.Request(f"{EP}?{urllib.parse.urlencode(p)}", headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8")).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 404: return []
            if att < 3: time.sleep(1.2 * (att + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if att < 3: time.sleep(1.2 * (att + 1)); continue
            raise


def fetch(dongs):
    """dongs: list of (code, name). return {code: data}"""
    out = {}
    for i, (code, name) in enumerate(dongs, 1):
        cp = os.path.join(CACHE, f"{code}.json")
        if os.path.exists(cp):
            out[code] = json.load(open(cp, encoding="utf-8")).get("data") or []
            continue
        data = call_api(code[:2], code[2:5], name)
        json.dump({"code": code, "name": name, "data": data}, open(cp, "w", encoding="utf-8"), ensure_ascii=False)
        out[code] = data
        if i % 40 == 0: print(f"  {i}/{len(dongs)} …")
        time.sleep(0.1)
    return out


def build_pool(raw):
    rows = []
    for dc, data in raw.items():
        for it in data:
            rows.append({"dl_id": f"{it['substCd']}:{it['dlCd']}", "dong": dc, "substCd": it.get("substCd"),
                         "mtrNo": it.get("mtrNo"), "vol1": num(it.get("vol1")), "vol2": num(it.get("vol2")), "vol3": num(it.get("vol3"))})
    seen, ded = set(), []
    for r in rows:
        k = (r["dl_id"], r["dong"])
        if k in seen: continue
        seen.add(k); ded.append(r)
    by_dl = defaultdict(list)
    for r in ded: by_dl[r["dl_id"]].append(r)
    contribs = defaultdict(list)
    for dl, rs in by_dl.items():
        valid = [r for r in rs if r["vol3"] is not None]
        n = len(valid)
        if not n: continue
        for r in valid:
            contribs[r["dong"]].append({"share": r["vol3"]/n, "mtr": f"{r['substCd']}:{r['mtrNo']}",
                                        "v2": r["vol2"], "sub": r["substCd"], "v1": r["vol1"]})
    pool = {}
    for dc, cs in contribs.items():
        capped = False; by_sub = defaultdict(list)
        for c in cs: by_sub[c["sub"]].append(c)
        final = 0.0
        for sk, sc in by_sub.items():
            by_m = defaultdict(list)
            for c in sc: by_m[c["mtr"]].append(c)
            after = 0.0
            for mk, g in by_m.items():
                ms = sum(c["share"] for c in g); v2 = g[0]["v2"]
                if v2 is not None and ms > v2: capped = True; after += v2
                else: after += ms
            v1 = sc[0]["v1"]
            if v1 is not None and after > v1: capped = True; final += v1
            else: final += after
        pool[dc] = (round(final, 1), capped)
    return pool


def main():
    a_feats = json.load(open(ABND, encoding="utf-8"))           # 338 (화성 제외)
    ch = json.load(open(CHORO, encoding="utf-8"))
    # 기존 choropleth에서 화성(41590) feature 보존
    hs = [f for f in ch["features"] if f["properties"]["dong"][:5] == "41590"]
    print(f"A 경계 {len(a_feats)}동 + 화성 기존 {len(hs)}동")

    # KEPCO 조회 대상 = A 경계 + 화성 기존
    dongs = [(f["properties"]["dong"], f["properties"]["name"]) for f in a_feats]
    dongs += [(f["properties"]["dong"], f["properties"]["name"]) for f in hs]
    raw = fetch(dongs)
    pool = build_pool(raw)
    print(f"pool 산출 {len(pool)}동")

    # 새 A features
    new_a = []
    for f in a_feats:
        code = f["properties"]["dong"]; kw, cap = pool.get(code, (0.0, False))
        new_a.append({"type":"Feature","properties":{"dong":code,"name":f["properties"]["name"],
                      "pool_mw":round(kw/1000,2),"capped":cap},"geometry":f["geometry"]})
    for f in hs:  # 화성: 기존 geometry + 재산출 pool
        code = f["properties"]["dong"]; kw, cap = pool.get(code, (0.0, False))
        new_a.append({"type":"Feature","properties":{"dong":code,"name":f["properties"]["name"],
                      "pool_mw":round(kw/1000,2),"capped":cap},"geometry":f["geometry"]})

    # B 유지, A 전량 교체
    b_feats = [f for f in ch["features"] if f["properties"]["dong"][:5] in B_PREF]
    ch["features"] = new_a + b_feats
    json.dump(ch, open(CHORO, "w", encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
    print(f"choropleth: A {len(new_a)} + B {len(b_feats)} = {len(ch['features'])}동")

    # summary A grid_pool_mw 재산출 (천안 44131+44133→44130)
    tot = defaultdict(float)
    for f in new_a:
        d = f["properties"]["dong"][:5]
        if d in ("44131","44133"): d = "44130"
        tot[d] += f["properties"]["pool_mw"] or 0
    sm = json.load(open(SUMM, encoding="utf-8"))
    print("\nA grid_pool_mw 재산출(기존→신):")
    for code in sorted(tot):
        if code in sm["codes"]:
            old = sm["codes"][code].get("grid_pool_mw")
            sm["codes"][code]["grid_pool_mw"] = round(tot[code], 1)
            print(f"  {code} {sm['codes'][code]['name']:8} {str(old):>8} → {round(tot[code],1)}")
    json.dump(sm, open(SUMM, "w", encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
    print("summary.json 갱신 완료")


if __name__ == "__main__":
    main()
