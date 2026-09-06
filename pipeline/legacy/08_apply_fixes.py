# -*- coding: utf-8 -*-
"""08_apply_fixes.py — 02 재실행 전 잔결함 해소 2건
=================================================================
1. 소유 재수집분(ownership_repair.csv, 2,425건) → parcels_clean 영구 반영
   (기존에는 최종본에만 패치돼 있어 02 재실행 시 유실됐음)
2. 보충본(복구 농지)의 용도지역(class1_name) 결측 → 토지특성 API(prposArea1Nm) 회수

사용: python 08_apply_fixes.py [workers=4]
"""
import os, sys, io, glob, time, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
CLEAN = os.path.join(OUT, "parcels_clean")
SUPP = os.path.join(OUT, "nojimok_repair", "supplement")
VWORLD_KEY = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
URL = "https://api.vworld.kr/ned/data/getLandCharacteristics"
WORKERS = next((int(a) for a in sys.argv[1:] if a.isdigit()), 4)


def step1_ownership():
    rep = pd.read_csv(os.path.join(OUT, "ownership_repair.csv"), dtype=str, encoding="utf-8-sig")
    rep["pnu"] = rep["pnu"].str.zfill(19)
    rep = rep.dropna(subset=["posesn"])
    m = rep.set_index("pnu")["posesn"]
    total = 0
    for f in sorted(glob.glob(os.path.join(CLEAN, "*.parquet"))):
        d = pd.read_parquet(f)
        d["pnu"] = d["pnu"].astype(str).str.zfill(19)
        na = d["ownership_name"].isna() | d["ownership_name"].astype(str).str.strip().isin(["", "nan", "None"])
        fix = na & d["pnu"].isin(m.index)
        if fix.any():
            d.loc[fix, "ownership_name"] = d.loc[fix, "pnu"].map(m)
            d.to_parquet(f, index=False)
            total += int(fix.sum())
            print(f"  {os.path.basename(f)}: 소유 반영 {int(fix.sum()):,}")
    print(f"[1] 소유 재수집 clean 반영 합계 {total:,} (기대 2,425)")


def fetch_uz(session, pnu):
    for y in ("2025", "2024"):
        try:
            r = session.get(URL, params={"key": VWORLD_KEY, "pnu": pnu, "stdrYear": y,
                                         "format": "json", "numOfRows": 3, "pageNo": 1,
                                         "domain": "localhost"}, timeout=10)
            if r.status_code != 200:
                return pnu, "ERR"
            j = r.json()
            body = j.get("landCharacteristicss")
            if body and (body.get("field") or []):
                return pnu, (body["field"][0].get("prposArea1Nm") or None)
        except Exception:
            return pnu, "ERR"
    return pnu, None  # 양 연도 모두 부재


def step2_use_zone():
    targets = {}
    for f in sorted(glob.glob(os.path.join(SUPP, "4*.parquet"))):
        d = pd.read_parquet(f)
        na = d["class1_name"].isna() | d["class1_name"].astype(str).str.strip().isin(["", "nan", "None"])
        targets[f] = d, na
    pnus = [p for (d, na) in targets.values() for p in d.loc[na, "pnu"]]
    print(f"[2] 용도지역 회수 대상 {len(pnus):,}")
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=WORKERS * 2))
    got, err = {}, 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fetch_uz, session, p) for p in pnus]
        for i, fut in enumerate(as_completed(futs), 1):
            pnu, v = fut.result()
            if v == "ERR":
                err += 1
            elif v:
                got[pnu] = v
            if i % 2000 == 0:
                print(f"  {i:,}/{len(pnus):,} 회수 {len(got):,} ERR {err:,} "
                      f"({i/(time.time()-t0):.0f}건/s)", flush=True)
    print(f"  회수 {len(got):,} / 부재 {len(pnus)-len(got)-err:,} / ERR {err:,}")
    for f, (d, na) in targets.items():
        fill = d["pnu"].map(got)
        d.loc[na & fill.notna(), "class1_name"] = fill[na & fill.notna()]
        d.to_parquet(f, index=False)
    print("[2] supplement class1_name 갱신 완료")


if __name__ == "__main__":
    if "step2" in sys.argv:
        step2_use_zone()  # 잔여 결측만 재시도 (멱등)
    else:
        step1_ownership()
        step2_use_zone()
