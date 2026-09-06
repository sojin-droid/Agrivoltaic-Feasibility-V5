# -*- coding: utf-8 -*-
"""10_collect_new_regions.py — 미보유 영역 본 수집 (A안, 2026-07-14 착수 승인)
=================================================================
대상: 예산군 44810 / 용인 처인구 41461 / 용인 수지구 41465 / 안산 단원구 41273
전략(무후회 순서): 두 경로(LX 252세트 입수 여부) 공통분부터 —
  Phase A (wfs):    연속지적 WFS 법정동리별 전수 — PNU·지번(지목 파싱)·geometry
  Phase B (ladfrl): 지목 미상분 토지대장 보완 (지목+소유 동시 회수)
  이후: LX DB 입수 시 속성 조인 / 미입수 시 농지 소유 ladfrl 확장 (별도 실행)
출력: pipeline_out/new_regions/collect.sqlite
  parcels(pnu PK, bjd, jibun, jimok_cd, jimok_nm, geojson, src)
  bjd_done(bjd PK, n)  — 체크포인트 (리 단위 재개)
사용:
  python 10_collect_new_regions.py wfs    [workers=3]
  python 10_collect_new_regions.py ladfrl [workers=4]
"""
import os, sys, io, re, json, sqlite3, time, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = r"C:\Users\user\새 폴더"
OUT_DIR = os.path.join(BASE, "pipeline_out", "new_regions")
DB = os.path.join(OUT_DIR, "collect.sqlite")
BJD_CSV = os.path.join(BASE, "pipeline_out", "bjd_codes_20250805.csv")  # 법정동코드 사본
os.makedirs(OUT_DIR, exist_ok=True)

VK = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
WFS_URL = "https://api.vworld.kr/req/wfs"
NED_LADFRL = "https://api.vworld.kr/ned/data/ladfrlList"
SGGS = {"44810": "예산", "41461": "용인처인", "41465": "용인수지", "41273": "안산단원"}
if os.environ.get("B_REGIONS") == "1":  # 2026-07-16 B 지역 완전 수집 (구미 진단 통과 후 착수)
    SGGS = {"28200": "인천남동", "46230": "광양", "46130": "여수", "47111": "포항남",
            "47113": "포항북", "47190": "구미", "31110": "울산중", "31140": "울산남",
            "31170": "울산동", "31200": "울산북", "31710": "울주"}
    DB = os.path.join(OUT_DIR, "collect_b.sqlite")
JIMOK = {"전": "01", "답": "02", "과": "03", "과수원": "03", "목": "04", "목장용지": "04",
         "임": "05", "임야": "05", "광": "06", "염": "07", "대": "08", "공": "09",
         "장": "09", "학": "10", "차": "11", "주": "12", "창": "13", "도": "14",
         "철": "15", "제": "16", "천": "17", "구": "18", "유": "19", "양": "20",
         "수": "21", "원": "22", "체": "23", "유원지": "24", "종": "25", "사": "26",
         "묘": "27", "잡": "28", "잡종지": "28"}
FARM_CD = {"01", "02", "03"}


def make_session(workers):
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=workers * 2))
    return s


def parse_jimok(jibun):
    m = re.search(r"([가-힣]+)$", (jibun or "").strip())
    if not m:
        return None, None
    nm = m.group(1)
    cd = JIMOK.get(nm)
    return (cd, nm) if cd else (None, nm)


def leaf_bjds():
    b = pd.read_csv(BJD_CSV, encoding="cp949", dtype=str)
    b = b[b["폐지여부"] == "존재"]
    codes = [c for c in b["법정동코드"] if c[:5] in SGGS and c[5:8] != "000"]
    # leaf = 리 코드(끝2!='00') + 하위 리가 없는 동 코드
    parents_with_kids = {c[:8] for c in codes if c[8:] != "00"}
    return sorted(c for c in codes
                  if c[8:] != "00" or c[:8] not in parents_with_kids)


def conn_init():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS parcels (
        pnu TEXT PRIMARY KEY, bjd TEXT, jibun TEXT, jimok_cd TEXT, jimok_nm TEXT,
        geojson TEXT, posesn_cd TEXT, posesn_nm TEXT, ar TEXT, src TEXT)""")
    conn.execute("CREATE TABLE IF NOT EXISTS bjd_done (bjd TEXT PRIMARY KEY, n INTEGER)")
    conn.commit()
    return conn


def _wfs_get(session, prefix, max_feat):
    filt = (f"<ogc:Filter xmlns:ogc='http://www.opengis.net/ogc'>"
            f"<ogc:PropertyIsLike wildCard='*' singleChar='.' escapeChar='!'>"
            f"<ogc:PropertyName>pnu</ogc:PropertyName><ogc:Literal>{prefix}*</ogc:Literal>"
            f"</ogc:PropertyIsLike></ogc:Filter>")
    r = session.get(WFS_URL, params={
        "service": "WFS", "version": "1.1.0", "request": "GetFeature",
        "typename": "lp_pa_cbnd_bubun", "key": VK,
        "outputFormat": "application/json", "srsName": "EPSG:4326",
        "maxFeatures": max_feat, "domain": "localhost", "filter": filt}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def fetch_prefix(session, bjd, prefix=None):
    """프리픽스 분할 수집. V-World WFS는 startIndex를 무시하므로(실측 2026-07-14)
    totalFeatures > 1000이면 PNU 자릿수를 늘려 재귀 분할한다. 반환 rows | None(오류)"""
    prefix = prefix or bjd
    try:
        j = _wfs_get(session, prefix, 1000)
    except Exception:
        return None
    feats = j.get("features", [])
    total = int(j.get("totalFeatures", 0))
    if total > len(feats):  # 한 페이지 초과 → 분할
        digits = "12" if len(prefix) == 10 else "0123456789"  # 11번째 자리=대장구분
        rows = []
        for d in digits:
            sub = fetch_prefix(session, bjd, prefix + d)
            if sub is None:
                return None
            rows.extend(sub)
        time.sleep(0.05)
        return rows
    rows = []
    for f in feats:
        p = f.get("properties", {})
        pnu = p.get("pnu", "")
        if len(pnu) != 19:
            continue
        cd, nm = parse_jimok(p.get("jibun"))
        keep_geom = (cd is None) or (cd in FARM_CD)  # 농지·미상만 geometry 보존
        rows.append({"pnu": pnu, "bjd": bjd, "jibun": p.get("jibun"),
                     "jimok_cd": cd, "jimok_nm": nm,
                     "geojson": json.dumps(f.get("geometry"), separators=(",", ":"))
                                if keep_geom and f.get("geometry") else None,
                     "src": "wfs"})
    return rows


fetch_bjd = fetch_prefix


def phase_wfs(workers):
    conn = conn_init()
    done = set(b for (b,) in conn.execute("SELECT bjd FROM bjd_done"))
    todo = [b for b in leaf_bjds() if b not in done]
    print(f"WFS 대상 법정동리 {len(todo)} (완료 {len(done)}) workers={workers}", flush=True)
    session = make_session(workers)
    lock = threading.Lock()
    n_row, n_err, t0 = 0, 0, time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_bjd, session, b): b for b in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            b = futs[fut]
            rows = fut.result()
            with lock:
                if rows is None:
                    n_err += 1
                else:
                    conn.executemany(
                        "INSERT OR REPLACE INTO parcels (pnu,bjd,jibun,jimok_cd,jimok_nm,geojson,src) "
                        "VALUES (:pnu,:bjd,:jibun,:jimok_cd,:jimok_nm,:geojson,:src)", rows)
                    conn.execute("INSERT OR REPLACE INTO bjd_done VALUES (?,?)", (b, len(rows)))
                    conn.commit()
                    n_row += len(rows)
            if i % 25 == 0:
                print(f"  {i}/{len(todo)} 리 완료 / 필지 {n_row:,} / 리오류 {n_err} "
                      f"({(time.time()-t0)/60:.1f}분)", flush=True)
    print(f"\nWFS 완료: 필지 {n_row:,} / 리 오류 {n_err} (재실행 시 이어받기) "
          f"/ {(time.time()-t0)/60:.1f}분", flush=True)
    st = pd.read_sql("SELECT substr(pnu,1,5) sgg, COUNT(*) n, "
                     "SUM(jimok_cd IS NULL) 지목미상, "
                     "SUM(jimok_cd IN ('01','02','03')) 전답과 FROM parcels GROUP BY 1", conn)
    print(st.to_string(index=False))
    conn.close()


def fetch_ladfrl(session, pnu):
    try:
        r = session.get(NED_LADFRL, params={"key": VK, "pnu": pnu, "format": "json",
                                            "numOfRows": 3, "pageNo": 1,
                                            "domain": "localhost"}, timeout=12)
        if r.status_code != 200:
            return {"pnu": pnu, "st": "ERR"}
        j = r.json()
        body = j.get("ladfrlVOList")
        if body is not None:
            rows = body.get("ladfrlVOList") or []
            if rows:
                v = rows[0]
                return {"pnu": pnu, "st": "OK", "cd": v.get("lndcgrCode"),
                        "nm": v.get("lndcgrCodeNm"), "pc": v.get("posesnSeCode"),
                        "pn": v.get("posesnSeCodeNm"), "ar": v.get("lndpclAr")}
            return {"pnu": pnu, "st": "NODATA"}
        if str(j.get("response", {}).get("totalCount", "")) == "0":
            return {"pnu": pnu, "st": "NODATA"}
        return {"pnu": pnu, "st": "ERR"}
    except Exception:
        return {"pnu": pnu, "st": "ERR"}


def phase_ladfrl(workers):
    conn = conn_init()
    pnus = [p for (p,) in conn.execute(
        "SELECT pnu FROM parcels WHERE jimok_cd IS NULL AND src='wfs'")]
    print(f"ladfrl 보완 대상(지목 미상) {len(pnus):,} workers={workers}", flush=True)
    session = make_session(workers)
    lock = threading.Lock()
    n_ok = n_nd = n_err = consec = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_ladfrl, session, p) for p in pnus]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            with lock:
                if r["st"] == "OK":
                    conn.execute("UPDATE parcels SET jimok_cd=?, jimok_nm=?, posesn_cd=?, "
                                 "posesn_nm=?, ar=?, src='wfs+ladfrl' WHERE pnu=?",
                                 (r["cd"], r["nm"], r["pc"], r["pn"], r["ar"], r["pnu"]))
                    n_ok += 1; consec = 0
                elif r["st"] == "NODATA":
                    conn.execute("UPDATE parcels SET src='wfs+nodata' WHERE pnu=?", (r["pnu"],))
                    n_nd += 1; consec = 0
                else:
                    n_err += 1; consec += 1
                if i % 400 == 0:
                    conn.commit()
            if i % 2000 == 0:
                el = time.time() - t0
                print(f"  {i:,}/{len(pnus):,} OK {n_ok:,} 소멸 {n_nd:,} ERR {n_err:,} "
                      f"({i/el:.0f}건/s)", flush=True)
            if consec >= 100:
                print("연속 오류 100 — 쿼터/장애 추정, 중단(재실행 이어받기)", flush=True)
                for f in futs:
                    f.cancel()
                break
    conn.commit()
    print(f"\nladfrl 완료: OK {n_ok:,} / 대장없음 {n_nd:,} / ERR {n_err:,} "
          f"/ {(time.time()-t0)/60:.1f}분", flush=True)
    conn.close()


def phase_own(workers):
    """농지 필지 소유구분 수집 (LX 252세트 입수 시 불필요 — 입수 즉시 중단 가능, 재개형)"""
    conn = conn_init()
    pnus = [p for (p,) in conn.execute(
        "SELECT pnu FROM parcels WHERE jimok_cd IN ('01','02','03') "
        "AND posesn_cd IS NULL AND src NOT LIKE '%nodata%'")]
    print(f"소유 수집 대상(전답과) {len(pnus):,} workers={workers}", flush=True)
    session = make_session(workers)
    lock = threading.Lock()
    n_ok = n_nd = n_err = consec = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_ladfrl, session, p) for p in pnus]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            with lock:
                if r["st"] == "OK":
                    conn.execute("UPDATE parcels SET posesn_cd=?, posesn_nm=?, ar=? WHERE pnu=?",
                                 (r["pc"], r["pn"], r["ar"], r["pnu"]))
                    n_ok += 1; consec = 0
                elif r["st"] == "NODATA":
                    conn.execute("UPDATE parcels SET posesn_cd='ND' WHERE pnu=?", (r["pnu"],))
                    n_nd += 1; consec = 0
                else:
                    n_err += 1; consec += 1
                if i % 500 == 0:
                    conn.commit()
            if i % 5000 == 0:
                el = time.time() - t0
                print(f"  {i:,}/{len(pnus):,} OK {n_ok:,} 대장없음 {n_nd:,} ERR {n_err:,} "
                      f"({i/el:.0f}건/s, 잔여 {(len(pnus)-i)/(i/el)/60:.0f}분)", flush=True)
            if consec >= 150:
                print("연속 오류 150 — 쿼터/장애 추정, 중단(재실행 이어받기)", flush=True)
                for f in futs:
                    f.cancel()
                break
    conn.commit()
    print(f"\n소유 수집: OK {n_ok:,} / 대장없음 {n_nd:,} / ERR {n_err:,} "
          f"/ {(time.time()-t0)/60:.1f}분", flush=True)
    conn.close()


def phase_sweep(workers):
    """법정동 목록 무의존 전수 수집: 시군 코드에서 프리픽스 재귀 분할.
    (법정동코드 개편·신설 코드에 면역 — 양지읍 41461262* 누락 사고의 근본 해결)"""
    conn = conn_init()
    session = make_session(4)
    for sgg, nm in SGGS.items():
        t0 = time.time()
        rows = fetch_prefix(session, sgg, prefix=sgg)
        if rows is None:
            print(f"  {sgg} {nm}: 스윕 실패 — 재실행 필요", flush=True)
            continue
        conn.executemany(
            "INSERT INTO parcels (pnu,bjd,jibun,jimok_cd,jimok_nm,geojson,src) "
            "VALUES (:pnu,:bjd,:jibun,:jimok_cd,:jimok_nm,:geojson,:src) "
            "ON CONFLICT(pnu) DO UPDATE SET bjd=excluded.bjd, jibun=excluded.jibun, "
            "jimok_cd=excluded.jimok_cd, jimok_nm=excluded.jimok_nm, "
            "geojson=excluded.geojson, src=excluded.src", rows)  # 소유 컬럼 보존
        conn.commit()
        print(f"  {sgg} {nm}: 스윕 {len(rows):,}건 ({(time.time()-t0)/60:.1f}분)", flush=True)
    st = pd.read_sql("SELECT substr(pnu,1,5) sgg, COUNT(*) n, "
                     "SUM(jimok_cd IN ('01','02','03')) 전답과, "
                     "SUM(jimok_cd IS NULL) 지목미상 FROM parcels GROUP BY 1", conn)
    print(st.to_string(index=False))
    conn.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "wfs"
    workers = next((int(a) for a in sys.argv[2:] if a.isdigit()), 3)
    {"wfs": phase_wfs, "ladfrl": phase_ladfrl, "own": phase_own,
     "sweep": phase_sweep}[mode](workers)
