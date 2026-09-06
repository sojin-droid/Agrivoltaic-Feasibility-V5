# -*- coding: utf-8 -*-
"""20_build_site_data.py — 배포용 site_v2/data 번들 생성 (단일 소스)
생성물: summary.json(코드별 판정·수요·계통) + pipeline_out/blocks/*.json 전량 복사.
(grid_dong.json·grid_choropleth.json은 본 스크립트가 만들지 않음 — 21/21e 산출, 2026-07-21 K13 정정)
천안=44130 단일(44131/44133 병합), A 노출.
2026-07-20: 출력 경로 site→site_v2 (site는 07-17 동결 구본 — 정본은 site_v2)."""
import os, sys, io, json, csv, shutil, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = r"C:\Users\user\새 폴더"
OUT = os.path.join(BASE, "pipeline_out")
SITE = os.path.join(BASE, "site_v2", "data")
os.makedirs(SITE, exist_ok=True)

# 생활권 병합 표시코드 (재분리 금지): 천안=44130 · 용인=41460 · 안산=41270 — 2026-07-22 일관 적용
NAMES = {"44270": "당진", "44180": "보령", "44200": "아산", "44130": "천안시", "44210": "서산",
         "44800": "홍성", "41590": "화성", "41220": "평택", "41460": "용인시", "41270": "안산시",
         "41390": "시흥", "41500": "이천", "41480": "파주", "41570": "김포", "44810": "예산",
         "28200": "인천남동",
         "46230": "광양", "46130": "여수", "47110": "포항시", "47190": "구미",
         "31000": "울산광역시"}
A = {"44270", "44180", "44200", "44130", "44210", "44800", "41590", "41220", "41460", "41270",
     "41390", "41500", "41480", "41570", "44810"}
GRID_MERGE = {"44130": ["44131", "44133"],
              "41460": ["41461", "41463", "41465"],
              "41270": ["41271", "41273"],
              "47110": ["47111", "47113"],
              "31000": ["31110", "31140", "31170", "31200", "31710"]}  # 계통(읍면동 pool)은 구별 분리값 → 합산
DEM_MERGE = GRID_MERGE  # 수요는 아래 demand_gwh()에서 중복 제거 병합 — 용인·안산은 구별 키에
# '시 전체' 동일값이 복제 배정돼 있어(kepco_demand scope 참조) 합산하면 2~3배 과대. 동일값은 1회만.

sw = json.load(open(os.path.join(OUT, "blocks_sweep_summary.json"), encoding="utf-8"))
dem = json.load(open(os.path.join(OUT, "kepco_demand.json"), encoding="utf-8"))["by_code"]
grid = {}
for r in csv.reader(open(os.path.join(OUT, "grid", "dong_pool.csv"), encoding="utf-8")):
    try:
        grid[r[2]] = grid.get(r[2], 0) + float(r[4]) / 1000
    except Exception:
        pass


def grid_mw(code):
    parts = GRID_MERGE.get(code, [code])
    vals = [grid[p] for p in parts if p in grid]
    return round(sum(vals), 1) if vals else None


def demand_gwh(code):
    v = dem.get(code, {}).get("total_gwh_year")
    if v is not None:
        return v
    vals = [dem.get(p, {}).get("total_gwh_year") for p in DEM_MERGE.get(code, [])]
    vals = [x for x in vals if x is not None]
    if not vals:
        return None
    # 구별 키에 '시 전체' 동일값이 복제된 경우(용인·안산) 1회만 반영; 상이한 실측 분할값이면 합산(천안 대비)
    uniq = {round(x, 2) for x in vals}
    return round(vals[0] if len(uniq) == 1 else sum(vals), 1)


out = {"generated": "2026-07-22", "codes": {}}
for code, nm in NAMES.items():
    v = sw.get(code, {})
    if not v:
        continue
    out["codes"][code] = {
        "name": nm, "region": "A" if code in A else "B",
        "S0": v.get("S0", {}), "S1": v.get("S1", {}), "S2": v.get("S2", {}),
        "demand_gwh": demand_gwh(code),
        "grid_pool_mw": grid_mw(code)}
json.dump(out, open(os.path.join(SITE, "summary.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))

# 블록 GeoJSON 복사 (A만 노출이지만 파일은 전부 두고 표시만 A — B 점등 대비)
n = 0
for f in glob.glob(os.path.join(OUT, "blocks", "*.json")):
    shutil.copy2(f, SITE)
    n += 1
print(f"summary.json: {len(out['codes'])}코드 (A {sum(1 for c in out['codes'] if out['codes'][c]['region']=='A')}) / blocks {n}개 복사")
print("천안 44130:", out["codes"]["44130"]["name"], out["codes"]["44130"]["S1"]["status_t30"],
      out["codes"]["44130"]["S1"]["b_mw_t30"], "MW / 수요", out["codes"]["44130"]["demand_gwh"],
      "/ 계통", out["codes"]["44130"]["grid_pool_mw"])
