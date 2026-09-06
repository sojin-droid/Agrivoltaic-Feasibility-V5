# -*- coding: utf-8 -*-
"""A 16개 시군 전체 법정동 경계 수집 + dissolve (B와 동일 방식, 읍면동 색칠 통일용)."""
import io, os, sys, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from collections import defaultdict

VK = "0EE07B70-6081-3E26-9B73-55E8D29E30AD"
A = {"44270":"당진","44180":"보령","44200":"아산","44210":"서산","44800":"홍성","44810":"예산",
     "41590":"화성","41220":"평택","41271":"안산상록","41390":"시흥","41461":"용인처인",
     "41480":"파주","41500":"이천","41570":"김포","44131":"천안동남","44133":"천안서북"}
OUT = r"C:\Users\user\새 폴더\pipeline_out\a_boundary_dongs.json"
S = requests.Session()

by_code, name_of = defaultdict(list), {}
for c, nm in A.items():
    filt = (f"<ogc:Filter xmlns:ogc='http://www.opengis.net/ogc'><ogc:PropertyIsLike "
            f"wildCard='*' singleChar='.' escapeChar='!'><ogc:PropertyName>emd_cd</ogc:PropertyName>"
            f"<ogc:Literal>{c}*</ogc:Literal></ogc:PropertyIsLike></ogc:Filter>")
    fs = []
    try:
        r = S.get("https://api.vworld.kr/req/wfs", params={"service":"WFS","version":"1.1.0",
            "request":"GetFeature","typename":"lt_c_ademd","key":VK,"outputFormat":"application/json",
            "maxFeatures":1000,"domain":"localhost","filter":filt,"srsName":"EPSG:4326"}, timeout=60)
        fs = r.json().get("features", [])
    except Exception as e:
        print(f"{c} {nm} ERR {str(e)[:40]}")
    for f in fs:
        code = f["properties"]["emd_cd"]
        by_code[code].append(shape(f["geometry"]))
        name_of[code] = f["properties"]["emd_kor_nm"]
    print(f"{c} {nm}: {len({k for k in by_code if k[:5]==c})}동")
    time.sleep(0.2)

feats = []
for code, geoms in by_code.items():
    g = unary_union(geoms).simplify(0.0003)
    feats.append({"type":"Feature","properties":{"dong":code,"name":name_of[code]},"geometry":mapping(g)})
json.dump(feats, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
print(f"\nA 법정동 경계: {len(feats)}동 → {OUT}")
