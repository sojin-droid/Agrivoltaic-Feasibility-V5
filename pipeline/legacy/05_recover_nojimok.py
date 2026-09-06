# -*- coding: utf-8 -*-
"""05_recover_nojimok.py — 지목 결측 112,579필지 복구 Phase A: 토지임야대장 지목 재조회
=================================================================
입력:  pipeline_out/coverage_nojimok_pnu.csv (커버리지 감사 산출)
API:   V-World NED ladfrlList (토지임야목록 — 지목·면적·소유·대장구분)
출력:  pipeline_out/nojimok_repair/ladfrl.sqlite (PNU별 결과, 재실행 시 이어받기)
       pipeline_out/nojimok_repair/phaseA_summary.md

사용:  python 05_recover_nojimok.py [workers=6]
중단:  연속 오류 80건(쿼터 소진 등) 시 자동 중단 — 재실행하면 이어서 수집
"""
import os, sys, io, sqlite3, time, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = r"C:\Users\user\새 폴더"
IN_CSV = os.environ.get("NOJIMOK_CSV",
                        os.path.join(BASE, "pipeline_out", "coverage_nojimok_pnu.csv"))
OUT_DIR = os.path.join(BASE, "pipeline_out", "nojimok_repair")
DB = os.environ.get("NOJIMOK_DB", os.path.join(OUT_DIR, "ladfrl.sqlite"))
os.makedirs(OUT_DIR, exist_ok=True)

VWORLD_KEY = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
URL = "https://api.vworld.kr/ned/data/ladfrlList"
WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
MAX_CONSEC_ERR = 80

FARM = {"전", "답", "과수원"}


def make_session():
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=WORKERS * 2))
    return s


# 전남광주통합특별시 개편(2026): 광양·여수는 신코드로 조회 (저장은 구코드 유지)
NEW_CODE = {"46230": "12190", "46130": "12130"}


def fetch(session, pnu):
    q_pnu = NEW_CODE.get(pnu[:5], pnu[:5]) + pnu[5:]
    try:
        r = session.get(URL, params={"key": VWORLD_KEY, "pnu": q_pnu, "format": "json",
                                     "numOfRows": 3, "pageNo": 1, "domain": "localhost"},
                        timeout=10)
        j = r.json()
    except Exception as e:
        return {"pnu": pnu, "status": "ERR", "err": str(e)[:120]}
    body = j.get("ladfrlVOList")
    if body is None:
        # totalCount 0 형태 ({"response": ...}) = 대장없음
        resp = j.get("response", {})
        if str(resp.get("totalCount", "")) == "0":
            return {"pnu": pnu, "status": "NODATA"}
        return {"pnu": pnu, "status": "ERR", "err": str(j)[:120]}
    rows = body.get("ladfrlVOList") or []
    if not rows:
        return {"pnu": pnu, "status": "NODATA"}
    v = rows[0]  # PNU 유일 (필지구분은 PNU 11번째 자리에 내재)
    return {"pnu": pnu, "status": "OK",
            "lndcgr_cd": v.get("lndcgrCode"), "lndcgr_nm": v.get("lndcgrCodeNm"),
            "posesn_cd": v.get("posesnSeCode"), "posesn_nm": v.get("posesnSeCodeNm"),
            "ar": v.get("lndpclAr"), "regstr_cd": v.get("regstrSeCode"),
            "ld_code": v.get("ldCode"), "last_updt": v.get("lastUpdtDt")}


def main():
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS repair (
        pnu TEXT PRIMARY KEY, status TEXT, lndcgr_cd TEXT, lndcgr_nm TEXT,
        posesn_cd TEXT, posesn_nm TEXT, ar TEXT, regstr_cd TEXT,
        ld_code TEXT, last_updt TEXT, err TEXT)""")
    conn.commit()

    todo = pd.read_csv(IN_CSV, dtype={"pnu": str, "sgg": str})
    todo["pnu"] = todo["pnu"].str.zfill(19)
    done = set(p for (p,) in conn.execute("SELECT pnu FROM repair WHERE status IN ('OK','NODATA')"))
    # ERR는 재시도 대상으로 남김
    conn.execute("DELETE FROM repair WHERE status='ERR'")
    conn.commit()
    pnus = [p for p in todo["pnu"] if p not in done]
    print(f"대상 {len(todo):,} / 완료 {len(done):,} / 이번 실행 {len(pnus):,} (workers={WORKERS})", flush=True)

    session = make_session()
    consec_err, n_ok, n_nodata, n_err = 0, 0, 0, 0
    buf, lock = [], threading.Lock()
    abort = False

    def flush():
        nonlocal buf
        if not buf:
            return
        conn.executemany("""INSERT OR REPLACE INTO repair
            (pnu,status,lndcgr_cd,lndcgr_nm,posesn_cd,posesn_nm,ar,regstr_cd,ld_code,last_updt,err)
            VALUES (:pnu,:status,:lndcgr_cd,:lndcgr_nm,:posesn_cd,:posesn_nm,:ar,:regstr_cd,:ld_code,:last_updt,:err)""",
            [{**{"lndcgr_cd": None, "lndcgr_nm": None, "posesn_cd": None, "posesn_nm": None,
                 "ar": None, "regstr_cd": None, "ld_code": None, "last_updt": None, "err": None}, **b}
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
                print(f"  {i:,}/{len(pnus):,} OK {n_ok:,} 대장없음 {n_nodata:,} ERR {n_err:,} "
                      f"({i/el:.1f}건/s, 잔여 {(len(pnus)-i)/(i/el)/60:.0f}분)", flush=True)
            if consec_err >= MAX_CONSEC_ERR:
                print(f"\n연속 오류 {MAX_CONSEC_ERR}건 — 쿼터 소진 추정, 중단. 재실행 시 이어받기.", flush=True)
                abort = True
                for f in futs:
                    f.cancel()
                break
    with lock:
        flush()

    # 요약
    df = pd.read_sql("SELECT * FROM repair", conn)
    df["sgg"] = df["pnu"].str[:5]
    farm = df[df["lndcgr_nm"].isin(FARM)]
    lines = [f"# Phase A 요약 — 지목 재조회 ({'중단됨(이어받기 필요)' if abort else '완료'})",
             f"- 처리 {len(df):,} / 대상 {len(todo):,} | OK {(df.status=='OK').sum():,} / "
             f"대장없음 {(df.status=='NODATA').sum():,} / ERR {(df.status=='ERR').sum():,}",
             f"- **전·답·과수원 판별 {len(farm):,}건** (Phase B geometry 수집 대상)", "",
             "## 시군 x 지목(상위)", "```",
             df.groupby(["sgg", "lndcgr_nm"]).size().unstack(fill_value=0).to_string(), "```", "",
             "## 시군별 농지 복구 vs 감사 부족분", "```",
             farm.groupby("sgg").size().to_string(), "```"]
    with open(os.path.join(OUT_DIR, "phaseA_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n총 {len(df):,} 처리 / 농지 판별 {len(farm):,} / {(time.time()-t0)/60:.1f}분")
    print("요약: pipeline_out/nojimok_repair/phaseA_summary.md")
    conn.close()


if __name__ == "__main__":
    main()
