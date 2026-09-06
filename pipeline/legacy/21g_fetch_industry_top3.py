# -*- coding: utf-8 -*-
"""29개 코드 산업분류별 전력사용량 TOP3 수집 (2025년 12개월 합산).
KEPCO powerUsage/industryType.do — 알려진 특례: 포항 시단위만(47113←47111),
천안 44130은 130 실패 시 131+133 병합. 출력: site_v2/data/sgg_industry.json
{code: [[업종약칭, 비중%], ...top3]}"""
import io, os, sys, json, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KEY = "a34NyPj52OjRf02fswjZU0125148Vaq5eS41A43k"
EP = "https://bigdata.kepco.co.kr/openapi/v1/powerUsage/industryType.do"
OUT = r"C:\Users\user\새 폴더\site_v2\data\sgg_industry.json"
CACHE = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-----\c890d164-6976-4299-b22a-aec933f33bbb\scratchpad\kepco_ind_cache.json"

CODES = ["44270","44180","44200","44130","44210","44800","41590","41220","41463","41271",
         "41390","41500","41480","41570","44810","41461","41465","41273",
         "28200","46230","46130","47111","47113","47190","31110","31140","31170","31200","31710"]
ALIAS = {"47113": ["47111"], "44130": ["44131+44133"],
         "41463": ["41461"], "41465": ["41461"], "41273": ["41271"]}   # 실패 시 폴백(KEPCO는 시 전체를 대표 구코드에 적재)
PREFIX = [("제조","제조"),("농업","농림어업"),("전기","전기가스"),("부동산","부동산"),("도매","도소매"),
 ("수도","수도재생"),("운수","운수"),("숙박","숙박음식"),("교육","교육"),("정보통신","정보통신"),
 ("국제","국제기관"),("광업","광업"),("보건","보건복지"),("건설","건설"),("금융","금융보험"),
 ("공공","공공행정"),("예술","예술여가"),("사업시설","사업시설"),("협회","기타서비스"),("가구","가구내")]
def short(b):
    for pre, s in PREFIX:
        if b.startswith(pre): return s
    return b[:4]


def call(y, m, metro, city):
    p = {"year": y, "month": m, "metroCd": metro, "cityCd": city, "apiKey": KEY, "returnType": "json"}
    url = f"{EP}?{urllib.parse.urlencode(p)}"
    for att in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as r:
                return json.loads(r.read().decode("utf-8")).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 404: return []
            if att < 4: time.sleep(1.2*(att+1)); continue
            raise
        except Exception:
            if att < 4: time.sleep(1.2*(att+1)); continue
            raise


def year_by_biz(metro, city):
    agg = defaultdict(float)
    for m in range(1, 13):
        for x in call("2025", f"{m:02d}", metro, city):
            agg[x.get("biz", "?")] += x.get("powerUsage", 0)
        time.sleep(0.04)
    return agg


cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
out = {}
for code in CODES:
    key = code
    if key in cache:
        agg = cache[key]
    else:
        cands = [code] + ALIAS.get(code, [])
        agg = {}
        for cand in cands:
            if "+" in cand:                       # 병합 폴백 (천안)
                merged = defaultdict(float)
                for cc in cand.split("+"):
                    for b, v in year_by_biz(cc[:2], cc[2:5]).items(): merged[b] += v
                agg = dict(merged)
            else:
                agg = dict(year_by_biz(cand[:2], cand[2:5]))
            if sum(agg.values()) > 0: break
        cache[key] = agg
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    tot = sum(agg.values())
    if tot <= 0:
        out[code] = None; print(f"{code}: 데이터 없음"); continue
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:3]
    out[code] = [[short(b), round(v/tot*100, 1)] for b, v in top]
    print(f"{code}: " + " · ".join(f"{n} {p}%" for n, p in out[code]))

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n→ {OUT}")
