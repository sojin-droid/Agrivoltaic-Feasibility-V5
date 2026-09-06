# -*- coding: utf-8 -*-
"""05b_recover_hwaseong.py — Phase A2: 화성(41590) 무지목 재조회
NED ladfrlList에 화성시 대장 데이터가 없어(지역 공백) 토지특성 API로 대체.
stdrYear=2025 우선, 없으면 2024 폴백. 같은 ladfrl.sqlite에 병합 (src 컬럼 구분).
사용: python 05b_recover_hwaseong.py [workers=6]
"""
import os, sys, io, sqlite3, time, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = r"C:\Users\user\새 폴더"
DB = os.path.join(BASE, "pipeline_out", "nojimok_repair", "ladfrl.sqlite")
VWORLD_KEY = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
URL = "https://api.vworld.kr/ned/data/getLandCharacteristics"
WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
MAX_CONSEC_ERR = 80
FARM = {"전", "답", "과수원"}


def make_session():
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=WORKERS * 2))
    return s


def query_year(session, pnu, year):
    """반환: dict(자료) | 'EMPTY'(명시적 totalCount 0) — 그 외는 예외 (오류를 부재로 오분류 금지)"""
    r = session.get(URL, params={"key": VWORLD_KEY, "pnu": pnu, "stdrYear": year,
                                 "format": "json", "numOfRows": 3, "pageNo": 1,
                                 "domain": "localhost"}, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    j = r.json()
    body = j.get("landCharacteristicss")
    if body is not None:
        rows = body.get("field") or []
        if rows:
            return rows[0]
        return "EMPTY"
    resp = j.get("response", {})
    if str(resp.get("totalCount", "")) == "0":
        return "EMPTY"
    raise RuntimeError(f"unexpected body: {str(j)[:80]}")


def fetch(session, pnu):
    try:
        v = query_year(session, pnu, "2025")
        if v == "EMPTY":
            v = query_year(session, pnu, "2024")
    except Exception as e:
        return {"pnu": pnu, "status": "ERR", "err": str(e)[:120]}
    if v == "EMPTY":
        return {"pnu": pnu, "status": "NODATA", "src": "특성"}
    return {"pnu": pnu, "status": "OK", "src": f"특성{v.get('stdrYear')}",
            "lndcgr_cd": v.get("lndcgrCode"), "lndcgr_nm": v.get("lndcgrCodeNm"),
            "ar": v.get("lndpclAr"), "ld_code": v.get("ldCode"),
            "use_zone1": v.get("prposArea1Nm"), "last_updt": v.get("lastUpdtDt")}


def main():
    t0 = time.time()
    conn = sqlite3.connect(DB)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(repair)")]
    for c in ("src", "use_zone1"):
        if c not in cols:
            conn.execute(f"ALTER TABLE repair ADD COLUMN {c} TEXT")
    conn.commit()

    # 대상: 화성 잔여 ERR만 (엄밀 판정 후 NODATA=명시적 부재로 확정)
    pnus = [p for (p,) in conn.execute(
        "SELECT pnu FROM repair WHERE substr(pnu,1,5)='41590' AND status='ERR'")]
    print(f"화성 재조회 대상 {len(pnus):,} (workers={WORKERS})", flush=True)

    session = make_session()
    consec_err, n_ok, n_nodata, n_err = 0, 0, 0, 0
    buf, lock = [], threading.Lock()

    def flush():
        nonlocal buf
        if not buf:
            return
        conn.executemany("""INSERT OR REPLACE INTO repair
            (pnu,status,lndcgr_cd,lndcgr_nm,posesn_cd,posesn_nm,ar,regstr_cd,ld_code,last_updt,err,src,use_zone1)
            VALUES (:pnu,:status,:lndcgr_cd,:lndcgr_nm,NULL,NULL,:ar,NULL,:ld_code,:last_updt,:err,:src,:use_zone1)""",
            [{**{"lndcgr_cd": None, "lndcgr_nm": None, "ar": None, "ld_code": None,
                 "last_updt": None, "err": None, "src": "특성", "use_zone1": None}, **b}
             for b in buf])
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
                elif r["status"] == "NODATA":
                    n_nodata += 1; consec_err = 0
                else:
                    n_err += 1; consec_err += 1
                if len(buf) >= 500:
                    flush()
            if i % 2000 == 0:
                el = time.time() - t0
                print(f"  {i:,}/{len(pnus):,} OK {n_ok:,} 없음 {n_nodata:,} ERR {n_err:,} "
                      f"({i/el:.1f}건/s)", flush=True)
            if consec_err >= MAX_CONSEC_ERR:
                print("연속 오류 — 중단(재실행 시 이어받기)", flush=True)
                for f in futs:
                    f.cancel()
                break
    with lock:
        flush()

    df = pd.read_sql("SELECT * FROM repair WHERE substr(pnu,1,5)='41590'", conn)
    farm = df[df["lndcgr_nm"].isin(FARM)]
    print(f"\n화성 결과: OK {(df.status=='OK').sum():,} / 없음 {(df.status=='NODATA').sum():,} "
          f"/ ERR {(df.status=='ERR').sum():,} | 전답과 {len(farm):,}")
    print(df[df.status == 'OK']["lndcgr_nm"].value_counts().head(12).to_string())
    print(f"{(time.time()-t0)/60:.1f}분")
    conn.close()


if __name__ == "__main__":
    main()
