# -*- coding: utf-8 -*-
"""06_fetch_geometry.py — 지목 결측 복구 Phase B: 농지 판별 필지 geometry 수집
=================================================================
입력:  pipeline_out/nojimok_repair/ladfrl.sqlite (repair — 전·답·과수원 판별분)
API:   V-World req/data LP_PA_CBND_BUBUN (attrFilter=pnu, EPSG:4326 GeoJSON)
출력:  같은 sqlite 내 geom 테이블 (pnu PK, geojson) — 재실행 시 이어받기

사용:  python 06_fetch_geometry.py [workers=4]
"""
import os, sys, io, sqlite3, time, threading, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = r"C:\Users\user\새 폴더"
DB = os.path.join(BASE, "pipeline_out", "nojimok_repair", "ladfrl.sqlite")
VWORLD_KEY = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
URL = "https://api.vworld.kr/req/data"
WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
MAX_CONSEC_ERR = 100


def make_session():
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=WORKERS * 2))
    return s


def fetch(session, pnu):
    try:
        r = session.get(URL, params={"service": "data", "request": "GetFeature",
                                     "data": "LP_PA_CBND_BUBUN", "key": VWORLD_KEY,
                                     "attrFilter": f"pnu:=:{pnu}", "crs": "EPSG:4326",
                                     "format": "json", "domain": "localhost"}, timeout=15)
        if r.status_code != 200:
            return {"pnu": pnu, "status": "ERR", "geojson": None, "jibun": None,
                    "err": f"HTTP {r.status_code}"}
        j = r.json()
        resp = j.get("response", {})
        st = resp.get("status")
        if st == "NOT_FOUND":
            return {"pnu": pnu, "status": "NOTFOUND", "geojson": None, "jibun": None, "err": None}
        if st != "OK":
            return {"pnu": pnu, "status": "ERR", "geojson": None, "jibun": None,
                    "err": str(resp.get("error", st))[:120]}
        feats = resp["result"]["featureCollection"]["features"]
        if not feats:
            return {"pnu": pnu, "status": "NOTFOUND", "geojson": None, "jibun": None, "err": None}
        f0 = feats[0]
        return {"pnu": pnu, "status": "OK",
                "geojson": json.dumps(f0["geometry"], separators=(",", ":")),
                "jibun": (f0.get("properties") or {}).get("jibun"), "err": None}
    except Exception as e:
        return {"pnu": pnu, "status": "ERR", "geojson": None, "jibun": None, "err": str(e)[:120]}


def main():
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS geom (
        pnu TEXT PRIMARY KEY, status TEXT, geojson TEXT, jibun TEXT, err TEXT)""")
    conn.execute("DELETE FROM geom WHERE status='ERR'")
    conn.commit()
    done = set(p for (p,) in conn.execute("SELECT pnu FROM geom"))
    pnus = [p for (p,) in conn.execute(
        "SELECT pnu FROM repair WHERE lndcgr_nm IN ('전','답','과수원')") if p not in done]
    print(f"geometry 대상 {len(pnus):,} (완료 {len(done):,}, workers={WORKERS})", flush=True)

    session = make_session()
    consec_err, n_ok, n_nf, n_err = 0, 0, 0, 0
    buf, lock = [], threading.Lock()

    def flush():
        nonlocal buf
        if not buf:
            return
        conn.executemany("INSERT OR REPLACE INTO geom VALUES (:pnu,:status,:geojson,:jibun,:err)", buf)
        conn.commit()
        buf = []

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch, session, p): p for p in pnus}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            with lock:
                buf.append(r)
                if r["status"] == "OK":
                    n_ok += 1; consec_err = 0
                elif r["status"] == "NOTFOUND":
                    n_nf += 1; consec_err = 0
                else:
                    n_err += 1; consec_err += 1
                if len(buf) >= 300:
                    flush()
            if i % 2000 == 0:
                el = time.time() - t0
                print(f"  {i:,}/{len(pnus):,} OK {n_ok:,} 없음 {n_nf:,} ERR {n_err:,} "
                      f"({i/el:.1f}건/s, 잔여 {(len(pnus)-i)/(i/el)/60:.0f}분)", flush=True)
            if consec_err >= MAX_CONSEC_ERR:
                print("연속 오류 — 중단(재실행 시 이어받기)", flush=True)
                for f in futs:
                    f.cancel()
                break
    with lock:
        flush()

    import pandas as pd
    g = pd.read_sql("SELECT status, substr(pnu,1,5) sgg FROM geom", conn)
    print(f"\n합계: OK {(g.status=='OK').sum():,} / 지적도없음 {(g.status=='NOTFOUND').sum():,} "
          f"/ ERR {(g.status=='ERR').sum():,} | {(time.time()-t0)/60:.1f}분")
    print(g.groupby(['sgg', 'status']).size().unstack(fill_value=0).to_string())
    conn.close()


if __name__ == "__main__":
    main()
