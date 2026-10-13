# -*- coding: utf-8 -*-
"""cross_check.py — 병합 브리지의 하천·철도(·도로·구거) 횡단 판정 (04 병합 패스용)
연속지적(LP_PA_CBND_BUBUN) 지목 문자를 브리지 선분과 교차 판정. sqlite 캐시로
동일 좌표쌍 재조회 방지 (t 스윕 반복 실행 대비). API 불능 시 None 반환(허용 처리)."""
import os, json, sqlite3, threading
import requests
from pyproj import Transformer
from shapely.geometry import LineString, shape

BASE = r"C:\Users\user\새 폴더"
CACHE = os.path.join(BASE, "pipeline_out", "cross_cache.sqlite")
VK = os.environ.get("VWORLD_API_KEY")  # 브이월드 오픈API(vworld.kr)에서 발급한 본인 키 — 04_cluster 가 import 하므로 여기서 종료하지 않고 호출 시 확인
def _need_key():
    raise RuntimeError("VWORLD_API_KEY 환경 변수가 없습니다 — 브이월드 오픈API에서 인증키를 발급받아 설정하세요 (README '외부 API 키')")


_TRI = Transformer.from_crs(5186, 4326, always_xy=True)
_JX = {"도": "도로", "천": "하천", "구": "구거", "철": "철도"}
_lock = threading.Lock()
_conn = sqlite3.connect(CACHE, check_same_thread=False)
_conn.execute("CREATE TABLE IF NOT EXISTS cx (k TEXT PRIMARY KEY, v TEXT)")
_conn.commit()
_S = requests.Session()


def bridge_crossing(p1, p2):
    """p1,p2 = EPSG:5186 좌표. 반환 set(횡단 지목) | None(판정 불능)."""
    key = f"{p1[0]:.0f},{p1[1]:.0f},{p2[0]:.0f},{p2[1]:.0f}"
    with _lock:
        row = _conn.execute("SELECT v FROM cx WHERE k=?", (key,)).fetchone()
    if row:
        v = json.loads(row[0])
        return None if v is None else set(v)
    lon1, lat1 = _TRI.transform(*p1)
    lon2, lat2 = _TRI.transform(*p2)
    line = LineString([(lon1, lat1), (lon2, lat2)])
    pad = 0.0002
    bbox = (f"BOX({min(lon1,lon2)-pad},{min(lat1,lat2)-pad},"
            f"{max(lon1,lon2)+pad},{max(lat1,lat2)+pad})")
    vk = VK or _need_key()  # 재시도 루프의 except 에 삼켜지지 않도록 밖에서 확인
    types = None
    for _ in range(3):
        try:
            r = _S.get("https://api.vworld.kr/req/data", params={
                "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
                "key": vk, "geomFilter": bbox, "crs": "EPSG:4326", "format": "json",
                "numOfRows": 100, "domain": "localhost"}, timeout=15)
            resp = r.json().get("response", {})
            if resp.get("status") == "OK":
                types = set()
                for f in resp["result"]["featureCollection"]["features"]:
                    jb = (f["properties"].get("jibun") or "").strip()
                    if jb and jb[-1] in _JX and shape(f["geometry"]).intersects(line):
                        types.add(_JX[jb[-1]])
                break
            if resp.get("status") == "NOT_FOUND":
                types = set()
                break
        except Exception:
            continue
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO cx VALUES (?,?)",
                      (key, json.dumps(sorted(types) if types is not None else None)))
        _conn.commit()
    return types
