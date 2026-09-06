# -*- coding: utf-8 -*-
"""B 11개 시군 수요(산업분류별 전력사용량) KEPCO OpenAPI 수집 → kepco_demand.json 병합.

엔드포인트: bigdata.kepco.co.kr/openapi/v1/powerUsage/industryType.do (year·month 필수).
산식: A와 동일 — 2023.01~2025.12(36개월) powerUsage 합 ÷ 3 ÷ 1e6 = 연평균 GWh.
검증: 당진(44/270) 총수요 API 36개월 = 기존 xlsx 산출 6362.56 GWh 정확 일치 확인함.
광양·여수는 전남광주통합특별시 개편으로 코드가 46↔12 갈릴 수 있어 폴백 시도.
"""
import io, os, sys, json, time, urllib.parse, urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KEY = "a34NyPj52OjRf02fswjZU0125148Vaq5eS41A43k"
EP = "https://bigdata.kepco.co.kr/openapi/v1/powerUsage/industryType.do"
OUT = r"C:\Users\user\새 폴더\pipeline_out\kepco_demand.json"

# 판정코드 -> (metroCd, cityCd 후보들, scope명)
B = {
    "28200": ("28", ["200"], "인천 남동구"),
    "46230": ("46", ["230"], "광양시"),      # 46 우선, 실패 시 12/190
    "46130": ("46", ["130"], "여수시"),      # 46 우선, 실패 시 12/130
    "47111": ("47", ["111"], "포항시 전체(남구+북구 합산)"),   # KEPCO 수요는 포항 시 단위만
    "47113": ("47", ["111"], "포항시 전체(남구+북구 합산)"),   # 47113 무응답 → 47111(시전체) 배정
    "47190": ("47", ["190"], "구미시"),
    "31110": ("31", ["110"], "울산 중구"),
    "31140": ("31", ["140"], "울산 남구"),
    "31170": ("31", ["170"], "울산 동구"),
    "31200": ("31", ["200"], "울산 북구"),
    "31710": ("31", ["710"], "울주군"),
}
ALT = {"46230": ("12", "190"), "46130": ("12", "130")}
MONTHS = [(y, f"{m:02d}") for y in ("2023", "2024", "2025") for m in range(1, 13)]


def call(y, m, metro, city):
    p = {"year": y, "month": m, "metroCd": metro, "cityCd": city, "apiKey": KEY, "returnType": "json"}
    url = f"{EP}?{urllib.parse.urlencode(p)}"
    for attempt in range(5):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8")).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 404:      # 해당 지역/월 데이터 없음 = 빈 결과
                return []
            if e.code in (401, 429, 500, 502, 503) and attempt < 4:  # 일시적 스로틀 → 백오프 재시도
                time.sleep(1.5 * (attempt + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 4:
                time.sleep(1.5 * (attempt + 1)); continue
            raise


def collect(metro, city):
    tot = mfg = 0.0
    for y, m in MONTHS:
        d = call(y, m, metro, city)
        tot += sum(x.get("powerUsage", 0) for x in d)
        mfg += sum(x.get("powerUsage", 0) for x in d if x.get("biz") == "제조업")
        time.sleep(0.04)
    return tot, mfg


CACHE = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-----\c890d164-6976-4299-b22a-aec933f33bbb\scratchpad\kepco_b_demand_cache.json"
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

dj = json.load(open(OUT, encoding="utf-8"))
bc = dj["by_code"]
for code, (metro, cities, scope) in B.items():
    if code in cache:
        tot, mfg = cache[code]
    else:
        city = cities[0]
        tot, mfg = collect(metro, city)
        if tot == 0 and code in ALT:      # 개편 코드 폴백
            metro, city = ALT[code]
            tot, mfg = collect(metro, city)
        cache[code] = [tot, mfg]
        json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    bc[code] = {
        "total_gwh_year": round(tot / 3 / 1e6, 2),
        "manuf_gwh_year": round(mfg / 3 / 1e6, 2),
        "scope": scope,
        "files": ["KEPCO OpenAPI powerUsage/industryType 2023.01-2025.12"],
    }
    print(f"{code} {scope:12} 총 {bc[code]['total_gwh_year']:>10} GWh / 제조 {bc[code]['manuf_gwh_year']:>9} GWh")

json.dump(dj, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nkepco_demand.json 병합 완료: by_code {len(bc)}개")
