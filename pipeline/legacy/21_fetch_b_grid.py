# -*- coding: utf-8 -*-
"""
누락 14개 코드(용인기흥·수지·안산단원 + B 11) 동단위 계통여유(KEPCO 배전선로 hosting
capacity) 수집 → choropleth 병합.

KEPCO bigdata OpenAPI(dispersedGeneration.do)는 apiKey 파라미터가 '존재'만 하면(빈
문자열 허용) 인증 없이 전 지역 응답. A 지역 파이프라인(kepco_client→build_dl_dong_index
→build_dong_pool)과 동일 산식을 그대로 이식.

입력 : pipeline_out/grid_pending_dongs.json (V-World 읍면동 경계 517개 = 질의 대상)
캐시 : <scratch>/kepco_b_raw/<dong>.json
출력 : site/data/grid_choropleth.json 에 실제 pool_mw 병합
"""
import io, os, sys, json, time, csv, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EP = "https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do"
ROOT = r"C:\Users\user\새 폴더"
PENDING = os.path.join(ROOT, "pipeline_out", "grid_pending_dongs.json")
CHORO = os.path.join(ROOT, "site_v2", "data", "grid_choropleth.json")  # 2026-07-21 정정(K8): 정본 site_v2 (구 site\는 07-17 동결)
CACHE = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-----\c890d164-6976-4299-b22a-aec933f33bbb\scratchpad\kepco_b_raw"
os.makedirs(CACHE, exist_ok=True)


def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None


def call_api(metro, city, dong):
    p = {"metroCd": metro, "cityCd": city, "addrLidong": dong, "apiKey": "", "returnType": "json"}
    req = urllib.request.Request(f"{EP}?{urllib.parse.urlencode(p)}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8"))
            if str(j.get("errCd")) == "404":
                return {"data": []}
        except Exception:
            pass
        raise


def fetch_all(feats):
    """동별 KEPCO 원응답 수집(캐시). return dong_code -> data list"""
    out = {}
    n = len(feats)
    for i, f in enumerate(feats, 1):
        code = f["properties"]["dong"]; name = f["properties"]["name"]
        cp = os.path.join(CACHE, f"{code}.json")
        if os.path.exists(cp):
            out[code] = json.load(open(cp, encoding="utf-8")).get("data") or []
            continue
        try:
            body = call_api(code[:2], code[2:5], name)
        except Exception as e:
            print(f"  [{i}/{n}] {code} {name} FAIL {str(e)[:50]}"); continue
        data = body.get("data") or []
        json.dump({"code": code, "name": name, "data": data}, open(cp, "w", encoding="utf-8"), ensure_ascii=False)
        out[code] = data
        if i % 50 == 0: print(f"  {i}/{n} …")
        time.sleep(0.12)
    return out


def build_pool(raw_by_dong):
    """A 지역 build_dl_dong_index + build_dong_pool 산식 이식."""
    # 1) dl_dong_index rows
    rows = []
    for dong_code, data in raw_by_dong.items():
        for it in data:
            rows.append({
                "dl_id": f"{it['substCd']}:{it['dlCd']}", "dong_code": dong_code,
                "substCd": it.get("substCd"), "mtrNo": it.get("mtrNo"),
                "vol1": num(it.get("vol1")), "vol2": num(it.get("vol2")), "vol3": num(it.get("vol3")),
            })
    # dedup (dl_id, dong)
    seen, ded = set(), []
    for r in rows:
        k = (r["dl_id"], r["dong_code"])
        if k in seen: continue
        seen.add(k); ded.append(r)
    rows = ded

    # 2) equal_split: dl_id가 걸친 동 수로 vol3 균등분할
    by_dl = defaultdict(list)
    for r in rows: by_dl[r["dl_id"]].append(r)

    dong_contribs = defaultdict(list)
    for dl_id, dl_rows in by_dl.items():
        valid = [r for r in dl_rows if r["vol3"] is not None]
        n = len(valid)
        if not n: continue
        for r in valid:
            dong_contribs[r["dong_code"]].append({
                "share": r["vol3"] / n, "mtr_key": f"{r['substCd']}:{r['mtrNo']}",
                "vol2": r["vol2"], "subst_key": r["substCd"], "vol1": r["vol1"],
            })

    # 3) 계층 캡(vol2 변압기 → vol1 변전소)
    pool = {}
    for dong_code, contribs in dong_contribs.items():
        capped = False
        by_subst = defaultdict(list)
        for c in contribs: by_subst[c["subst_key"]].append(c)
        final = 0.0
        for sk, sc in by_subst.items():
            by_mtr = defaultdict(list)
            for c in sc: by_mtr[c["mtr_key"]].append(c)
            after = 0.0
            for mk, g in by_mtr.items():
                ms = sum(c["share"] for c in g); v2 = g[0]["vol2"]
                if v2 is not None and ms > v2: capped = True; after += v2
                else: after += ms
            v1 = sc[0]["vol1"]
            if v1 is not None and after > v1: capped = True; final += v1
            else: final += after
        pool[dong_code] = (round(final, 1), capped)
    return pool


def main():
    feats = json.load(open(PENDING, encoding="utf-8"))
    print(f"질의 대상 읍면동: {len(feats)}")
    raw = fetch_all(feats)
    got = sum(1 for v in raw.values() if v)
    print(f"KEPCO 응답 수집: {len(raw)}동 (DL 있음 {got}동)")
    pool = build_pool(raw)
    print(f"pool 산출: {len(pool)}동")

    # choropleth 병합
    ch = json.load(open(CHORO, encoding="utf-8"))
    have = {f["properties"]["dong"] for f in ch["features"]}
    added = 0
    for f in feats:
        code = f["properties"]["dong"]
        if code in have: continue
        kw, capped = pool.get(code, (None, False))
        pool_mw = round(kw / 1000, 2) if kw is not None else 0.0
        ch["features"].append({
            "type": "Feature",
            "properties": {"dong": code, "name": f["properties"]["name"],
                           "pool_mw": pool_mw, "capped": capped},
            "geometry": f["geometry"],
        })
        added += 1
    json.dump(ch, open(CHORO, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"choropleth 병합: +{added}동 → 총 {len(ch['features'])}동")
    # 코드별 요약
    from collections import Counter
    tot = defaultdict(float); cnt = Counter()
    for f in feats:
        code = f["properties"]["dong"]; kw, _ = pool.get(code, (None, False))
        tot[code[:5]] += (kw or 0) / 1000; cnt[code[:5]] += 1
    NM = {"41463":"용인기흥","41465":"용인수지","41273":"안산단원","28200":"인천남동","46230":"광양","46130":"여수","47111":"포항남","47113":"포항북","47190":"구미","31110":"울산중","31140":"울산남","31170":"울산동","31200":"울산북","31710":"울주"}
    print("\n코드별 계통여유 합계(MW):")
    for c in sorted(tot, key=lambda k: -tot[k]):
        print(f"  {c} {NM.get(c,''):8} {cnt[c]:2}동  {tot[c]:8.1f} MW")


if __name__ == "__main__":
    main()
