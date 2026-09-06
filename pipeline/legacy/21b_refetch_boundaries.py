# -*- coding: utf-8 -*-
"""누락 14코드 읍면동 경계 재수집 + 동코드별 dissolve(섬 폴리곤 통합)."""
import io, os, sys, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from collections import defaultdict

VK = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
MISS = {"41463":"용인기흥","41465":"용인수지","41273":"안산단원","28200":"인천남동",
        "46230":"광양","46130":"여수","47111":"포항남","47113":"포항북","47190":"구미",
        "31110":"울산중","31140":"울산남","31170":"울산동","31200":"울산북","31710":"울주"}
NEW = {"46230":"12190","46130":"12130"}
OUT = r"C:\Users\user\새 폴더\pipeline_out\grid_pending_dongs.json"
S = requests.Session()

by_code_geoms = defaultdict(list)
name_of = {}
for c, nm in MISS.items():
    pref = NEW.get(c, c)
    filt = (f"<ogc:Filter xmlns:ogc='http://www.opengis.net/ogc'><ogc:PropertyIsLike "
            f"wildCard='*' singleChar='.' escapeChar='!'><ogc:PropertyName>emd_cd</ogc:PropertyName>"
            f"<ogc:Literal>{pref}*</ogc:Literal></ogc:PropertyIsLike></ogc:Filter>")
    fs = []
    try:
        r = S.get("https://api.vworld.kr/req/wfs", params={"service":"WFS","version":"1.1.0",
            "request":"GetFeature","typename":"lt_c_ademd","key":VK,"outputFormat":"application/json",
            "maxFeatures":1000,"domain":"localhost","filter":filt,"srsName":"EPSG:4326"}, timeout=60)
        fs = r.json().get("features", [])
    except Exception as e:
        print(f"{c} {nm} ERR {str(e)[:40]}")
    for f in fs:
        p = f["properties"]; code = p.get("emd_cd", "")
        if pref != c: code = c + code[5:]          # 신코드→구코드
        by_code_geoms[code].append(shape(f["geometry"]))
        name_of[code] = p.get("emd_kor_nm")
    print(f"{c} {nm}: {len(fs)}폴리곤 → {len({k for k in by_code_geoms if k[:5]==c})}동")
    time.sleep(0.2)

feats = []
for code, geoms in by_code_geoms.items():
    g = unary_union(geoms).simplify(0.0003)
    feats.append({"type":"Feature",
        "properties":{"dong":code,"name":name_of[code],"pool_mw":None,"pending":True},
        "geometry": mapping(g)})
json.dump(feats, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
print(f"\ndissolve 완료: 고유 동 {len(feats)}개 → {OUT}")
