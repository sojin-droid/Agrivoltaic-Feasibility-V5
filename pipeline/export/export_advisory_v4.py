# -*- coding: utf-8 -*-
"""자문용(ADVISORY) 경기도 검토 자산 export — data_v4/advisory/gg_v1.json.gz (2026-09-27).

목적: 외부 자문(경기도 공간·농지·행정 / 공간분석·수학 방법론 / 지자체 사용성)이 원본 GIS 파일을 열지 않고도
     현재 21m 후보 공간 결과를 눈으로 검증할 수 있게 하는 **중간 인터페이스** 자산. 새 판정·새 점수·새 클러스터 없음.

원천(전부 기존 산출을 읽기만 한다)
  · Ledger_Rebuild/advisory_all_v1/<run>/block_context.parquet   경기도 후보 공간 **전량**(면적 하한 없음)의 맥락 축
        (계통 여유 lo/hi·산단 거리·대표점·간척 %·경작 비율) — build_advisory_all_v1.py 가 정본 엔진 block_context.build(take_all) 로 만든 것
        R0_current · R2_promo · R3_zone_all 세 조건
  · Ledger_Rebuild/advisory_all_v1/R2_promo/units.gpkg   같은 전량의 도형(v9_02 절차 그대로 · 기하 품질 등급 포함)
  · 2026-09-28 사용자 결정 — 11,111㎡(≈0.5MW) 하한은 근거 없는 임의 문턱이라 자문 자산에서 뺐다.
    비지배 플래그는 export_top10_v4.py 와 같은 규칙(전수 쌍별 비교 · query._frontier_mask 대조)으로 이 전량에서 다시 센다.
  · data_v4/existing_pv_v4.json.gz   기존 태양광 시설 위치(VALID 좌표만) — 후보 공간 폴리곤 안의 점 수를 **자문 표시용으로만** 센다
                                (정본 중첩 산출이 아니다 · 전국 전수 아님 · 점이 없다는 것은 시설 부재가 아니다)
  · data_v4/bjd_v4.json.gz       법정동 이름
  · data_v4/provenance_v4.json   자료별 수집·기준 시점·원천 판 표기

여기서 계산하는 것(표시·요약용 — 판정에 쓰지 않는다)
  · 세 축(A 면적 · B 계통 여유 참고값 lo · C 산단 거리)의 분포 통계와 Pearson·Spearman 상관 — 경기도 R2 고유 후보 공간 기준
  · 읍면동별 후보 공간 수·면적·10/20/50MW 등가 이상 수(관여 기준 — 읍면동끼리 더하지 않는다)
  · 자문 검토 사례: 선정 규칙을 자산에 함께 적는다(“좋은 지역” 선정이 아니다)
≤1,000m 응축(cc)은 쓰지 않는다 — 폐기된 계보이며 이 자산에 등장하지 않는다.
사용: python pipeline/export/export_advisory_v4.py
"""
import os, sys, json, gzip, glob, datetime, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR, MODEL
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
import duckdb
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

OUT = os.path.join(SITE, 'data_v4')
SIDO = '41'
RUNS = ['R0_current', 'R2_promo', 'R3_zone_all']
KW = 0.045                                             # kW/㎡ — 기존 환산 계수(ADR-0012). 새로 만들지 않는다.
BANDS = {'10': 222222, '20': 444444, '50': 1111111}    # 10·20·50MW 크기 구분(0.045 kW/㎡ 역산) — 법정 기준 아님
gz = lambda p: json.load(gzip.open(p, 'rt', encoding='utf-8'))

# 행정 이름 — 법정동코드(bjd_code, 폐지 포함)의 시군 행(코드 뒤 5자리 0)·읍면동 행(뒤 2자리 0)을 그대로 읽는다(이름 추정 없음)
_bc = duckdb.connect(os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb'), read_only=True)
NAME10 = dict(_bc.execute("SELECT code10, name_full FROM bjd_code WHERE SUBSTR(code10,6,5)='00000' OR SUBSTR(code10,9,2)='00'").fetchall())
_bc.close()
emd_name = lambda e8: NAME10.get(e8 + '00', e8)
sgg_name = lambda s: NAME10.get(s + '00000', s)

STAGE = os.path.join(LR, 'advisory_all_v1')
sys.path.insert(0, MODEL)
import pandas as pd, geopandas as gpd
from pyproj import Transformer
from shapely.geometry import mapping
import query as Q
FILTERS = [0, 66667, 222222, 444444, 1111111]     # 표시 규모 선택지(㎡) — export_top10_v4 와 동일
AXK = {'a': ('area_m2', +1), 'b': ('lo', +1), 'c': ('dist_ind_km', -1)}


def nondominated(d, axes):
    """export_top10_v4.nondominated 와 같은 규칙 — 전수 쌍별 지배 비교, 결측은 축 방향의 최악, 동률 ≠ 지배."""
    cols = [AXK[k] for k in axes]
    v = np.column_stack([d[c].to_numpy(float) for c, _ in cols]).astype(float)
    for j, (_, sgn) in enumerate(cols):
        v[:, j] = np.nan_to_num(v[:, j], nan=(-np.inf if sgn > 0 else np.inf)) * sgn
    dom = np.zeros(len(v), dtype=bool)
    for i in range(len(v)):
        dom[i] = bool((np.all(v >= v[i], axis=1) & np.any(v > v[i], axis=1)).any())
    return ~dom


def check(d, arr, fixed=None):
    dd = d.copy()
    if fixed: dd[fixed] = 0.0
    assert np.array_equal(arr, Q._frontier_mask(dd)), '[FAIL] 비지배 플래그 ≠ query._frontier_mask'


# ── 도형(R2 · 전량) ──
T = Transformer.from_crs(5186, 4326, always_xy=True)
rnd = lambda c: [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
G = gpd.read_file(os.path.join(STAGE, 'R2_promo', 'units.gpkg')).to_crs(4326)
units = {}
for r in G.itertuples():
    gm = mapping(r.geometry)
    units[int(r.lab)] = {'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])},
                         'properties': {'ag': round(float(r.area_geom_m2)), 't': str(r.display_tier), 'ql': str(r.quality_label)}}
print(f"경기도 후보 공간 도형(R2 · 전량) {len(units):,}")

# ── 소속 시군·읍면동(필지 기준 — 도형 유무와 무관) ──
mem = pd.read_parquet(os.path.join(STAGE, 'R2_promo', 'members.parquet'), columns=['pnu', 'lab'])
mem['sgg'] = mem.pnu.str[:5]; mem['emd'] = mem.pnu.str[:8]
SGGS = mem.groupby('lab').sgg.apply(lambda s: sorted(set(s))).to_dict()
EMDS = mem.groupby('lab').emd.apply(lambda s: sorted(set(s))).to_dict()

# ── 시군별 행 — 세 조건 · 전량(시군 관여 기준) ──
rows, fronts, labels = {r: {} for r in RUNS}, {r: {} for r in RUNS}, {}
n_chk = 0
for run in RUNS:
    bc = pd.read_parquet(os.path.join(STAGE, run, 'block_context.parquet'))
    bc = bc[bc.sgg.str.startswith(SIDO)]
    lon, lat = T.transform(bc['x'].to_numpy(float), bc['y'].to_numpy(float))
    bc = bc.assign(lon=lon, lat=lat)
    for sgg, d in bc.groupby('sgg'):
        d = d.sort_values(['area_m2', 'lab'], ascending=[False, True]).reset_index(drop=True)
        fl = {k: nondominated(d, a) for k, a in (('f3', 'abc'), ('fab', 'ab'), ('fac', 'ac'), ('fbc', 'bc'))}
        check(d, fl['f3']); check(d, fl['fab'], 'dist_ind_km'); check(d, fl['fac'], 'lo'); check(d, fl['fbc'], 'area_m2'); n_chk += 1
        nz = lambda v, k: None if pd.isna(v) else round(float(v), k)
        rows[run][sgg] = [{'lab': int(r.lab), 'a': round(float(r.area_m2)), 'mw': round(float(r.mw), 1), 'lo': nz(r.lo, 1), 'hi': nz(r.hi, 1),
                           'd': nz(r.dist_ind_km, 2), 'lat': nz(r.lat, 5), 'lon': nz(r.lon, 5), 'recl': nz(r.reclaim_pct, 0),
                           'n': int(r.n_parcel), 'ne': None if pd.isna(r.n_emd) else int(r.n_emd), 'farm': nz(r.farm_ratio, 3),
                           **{k: bool(fl[k][i]) for k in fl}} for i, r in enumerate(d.itertuples())]
        if run == 'R2_promo':
            fr = {}
            for th in FILTERS:
                sub = d[d['area_m2'] >= th].reset_index(drop=True)
                fr[str(th)] = {k: ([int(x) for x in sub['lab'][nondominated(sub, a)]] if len(sub) else [])
                               for k, a in (('f3', 'abc'), ('fab', 'ab'), ('fac', 'ac'), ('fbc', 'bc'))}
            fronts[run][sgg] = fr
        labels[sgg] = sgg_name(sgg).replace('경기도 ', '')
    print(f"{run}: 시군 {len(rows[run])} · 후보 공간 {bc.lab.nunique():,}(시군 관여 행 {len(bc):,})", flush=True)
print(f"비지배 플래그 4종 = query._frontier_mask 대조 통과 ({n_chk} 시군×조건)")

# ── 기존 시설(VALID 좌표) — 폴리곤 안 점 수(자문 표시용) ──
EX = gz(os.path.join(OUT, 'existing_pv_v4.json.gz'))
pts = [p for p in EX['pts'] if str(p[6]).startswith(SIDO)]
ids = list(units)
geoms = [shape(units[i]['geometry']) for i in ids]
tree = STRtree(geoms)
ex_in = {}
for p in pts:
    pt = Point(p[0], p[1])
    for k in tree.query(pt):
        if geoms[k].contains(pt):
            ex_in[ids[k]] = ex_in.get(ids[k], 0) + 1
print(f"기존 태양광 시설 점(경기) {len(pts):,} · 후보 공간 안에 점이 있는 곳 {len(ex_in):,}")

# ── 후보 공간 레코드(R2) — 시군별 행과 폴리곤을 lab 로 잇는다 ──
recs = {}
for sgg, rs in rows['R2_promo'].items():
    for r in rs:
        lab = r['lab']
        u = units.get(lab)
        p = u['properties'] if u else {}
        rec = recs.setdefault(lab, {
            'id': lab, 'sggs': SGGS.get(lab) or [sgg], 'emds': EMDS.get(lab) or [], 'a': r['a'], 'mw': r['mw'],
            'n': r['n'], 'lo': r['lo'], 'hi': r['hi'], 'd': r['d'], 'lat': r['lat'], 'lon': r['lon'], 'recl': r['recl'],
            'ne': r['ne'], 'ag': p.get('ag'), 't': p.get('t', 'missing'), 'ql': p.get('ql', '도형 없음(지적 폴리곤 없음)'),
            'farm': r['farm'], 'ex': ex_in.get(lab, 0), 'fl': {}})
        rec['fl'][sgg] = {k: r[k] for k in ('f3', 'fab', 'fac', 'fbc')}   # 비지배는 시군 안 비교(정본 정의) — 시군별로 따로
print(f"레코드 {len(recs):,} (폴리곤 없는 단위 {sum(1 for v in recs.values() if v['t'] == 'missing')})")


# ── 세 축 분포 통계(경기도 R2 고유 후보 공간) ──
def stats(vals):
    v = np.array([x for x in vals if x is not None], float)
    if not len(v):
        return None
    q = lambda p: float(np.percentile(v, p))
    return {'n': int(len(v)), 'n_missing': int(len(vals) - len(v)), 'min': float(v.min()), 'max': float(v.max()),
            'mean': float(v.mean()), 'median': q(50), 'std': float(v.std(ddof=1)) if len(v) > 1 else 0.0,
            'iqr': q(75) - q(25), 'p10': q(10), 'p25': q(25), 'p50': q(50), 'p75': q(75), 'p90': q(90)}


def rankdata(x):
    o = np.argsort(x, kind='mergesort'); r = np.empty(len(x)); r[o] = np.arange(len(x), dtype=float)
    xs = x[o]; i = 0
    while i < len(x):                                  # 동률은 평균 순위(스피어만 표준)
        j = i
        while j + 1 < len(x) and xs[j + 1] == xs[i]:
            j += 1
        r[o[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def corr(a, b):
    m = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(m) < 3:
        return None
    x, y = np.array([p[0] for p in m], float), np.array([p[1] for p in m], float)
    return {'n': len(m), 'pearson': float(np.corrcoef(x, y)[0, 1]), 'spearman': float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])}


V = list(recs.values())
A, Bv, Cv = [r['a'] / 1e6 for r in V], [r['lo'] for r in V], [r['d'] for r in V]
summary = {
    'population': '경기도 · 특별법 시행 후(농업진흥구역에 설치 가능 · 농업보호구역 제외) · 21m 후보 공간 전량(면적 하한 없음 · 시군 경계에 걸친 곳은 한 번만 셈)',
    'n_units': len(V), 'area_km2': round(sum(A), 3),
    'axes': {'A': {'name': '공간 규모', 'unit': 'km² (참고 MW = 면적 × 0.045 kW/㎡)', 'dir': '클수록', 'stats': stats(A)},
             'B': {'name': '계통 여유 참고값', 'unit': 'MW (소재 읍면동 잔여 연계가능용량 하한 — 같은 읍면동 후보는 같은 값)', 'dir': '클수록', 'stats': stats(Bv)},
             'C': {'name': '산업단지까지 거리', 'unit': 'km (최근접 산업단지 경계 직선거리)', 'dir': '가까울수록', 'stats': stats(Cv)}},
    'corr': {'A-B': corr(A, Bv), 'A-C': corr(A, Cv), 'B-C': corr(Bv, Cv)},
    'bands': {k: sum(1 for r in V if r['a'] >= m) for k, m in BANDS.items()},
    'nondominated': {k: sum(1 for r in V if any(f[k] for f in r['fl'].values())) for k in ('f3', 'fab', 'fac', 'fbc')},
    'geom': {t: sum(1 for r in V if r['t'] == t) for t in ('default', 'quality_review', 'missing')},
    'existing_in': sum(1 for r in V if r['ex'] > 0),
}

# ── 읍면동별 요약(관여 기준) ──
emd = {}
for r in V:
    for e in r['emds']:
        s = emd.setdefault(e, {'e': e, 'name': emd_name(e), 'k': 0, 'a': 0, 'b10': 0, 'b20': 0, 'b50': 0})
        s['k'] += 1; s['a'] += r['a']
        for k, m in BANDS.items():
            if r['a'] >= m:
                s['b' + k] += 1


# ── 자문 검토 사례(규칙 명시 · 결정적) ──
def pick(cands, key, rule):
    cands = sorted(cands, key=key)
    return (cands[0]['id'], rule) if cands else None


okg = [r for r in V if r['t'] != 'missing']
med = lambda xs: float(np.median([x['a'] for x in xs])) if xs else 0
mid = [r for r in okg if BANDS['10'] <= r['a'] < BANDS['50']]
sml = [r for r in okg if 66667 <= r['a'] < BANDS['10']]
cases = [c for c in [
    pick(okg, lambda r: (-r['a'], r['id']), '대규모 후보 사례 — 경기도에서 면적이 가장 큰 후보 공간'),
    pick(mid, lambda r: (abs(r['a'] - med(mid)), r['id']), '중간 규모 후보 사례 — 10–50MW 구간에서 면적이 구간 중앙값에 가장 가까운 후보 공간'),
    pick(sml, lambda r: (abs(r['a'] - med(sml)), r['id']), '작은 후보 사례 — 3–10MW 구간에서 면적이 구간 중앙값에 가장 가까운 후보 공간'),
    pick(okg, lambda r: (-(r['ne'] or 0), -len(r['sggs']), -r['a'], r['id']), '경계가 복잡한 사례 — 걸친 읍면동 수가 가장 많은 후보 공간'),
    pick([r for r in V if r['t'] == 'quality_review' and r['ag']], lambda r: (-abs(math.log(r['ag'] / r['a'])), r['id']),
         '기하 품질 검토 사례 — 지적 도형 면적과 장부 면적의 차이(비율)가 가장 큰 후보 공간'),
    pick([r for r in okg if r['lo'] is not None and r['hi'] is not None], lambda r: (-(r['hi'] - r['lo']), r['id']),
         '계통값 차이가 큰 사례 — 계통 여유 참고값의 하한과 상한 차이가 가장 큰 후보 공간'),
    pick([r for r in okg if r['d'] is not None and r['a'] >= BANDS['10']], lambda r: (r['d'], r['id']),
         '산업단지와 가까운 사례 — 10MW 이상 중 산업단지 경계까지 거리가 가장 짧은 후보 공간'),
    pick([r for r in okg if r['d'] is not None and r['a'] >= BANDS['10']], lambda r: (-r['d'], r['id']),
         '산업단지와 먼 사례 — 10MW 이상 중 산업단지 경계까지 거리가 가장 먼 후보 공간'),
] if c]

# ── 다른 가정(R0·R3)의 시군별 행 — 사용성 모드의 시나리오 전환용(점 표시 · 도형은 clusters/ 폴백) ──
alt = {r: {s: [[x['lab'], x['a'], x['mw'], x['lo'], x['d'], x['lat'], x['lon'], x['f3'], x['fab'], x['fac'], x['fbc']] for x in rs]
           for s, rs in rows[r].items()} for r in ('R0_current', 'R3_zone_all')}

P = json.load(open(os.path.join(OUT, 'provenance_v4.json'), encoding='utf-8'))
PC = P['cols']
PROV_IDS = ['raw:cadastre_all', 'raw:land_processed_zip', 'raw:agpromo_raw', 'raw:farmmap_2025', 'raw:regulation_composite',
            'raw:kepco_raw_v4', 'tbl:kepco_record_v3', 'raw:damdan_raw', 'tbl:ind_complex_bnd', 'raw:emd_bnd_raw',
            'tbl:analysis_unit_v1', 'tbl:existing_pv_v1', 'src:kpx_plants_raw', 'src:permit_raw', 'tbl:bjd_code']
prov = {r[0]: dict(zip(PC, r)) for r in P['rows'] if r[0] in PROV_IDS}

out = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'mode': 'ADVISORY — 자문용 검토 자산(최종 판정·순위가 아님)',
       'kw_per_m2': KW, 'bands_m2': BANDS, 'sgg_labels': labels, 'summary': summary,
       'emd': sorted(emd.values(), key=lambda s: s['e']), 'cases': [{'id': i, 'rule': r} for i, r in cases],
       # 도형은 시군별 파일(advisory/geom/{sgg}.json.gz)로 뺀다 — 전량 5만여 곳을 한 파일에 담으면 휴대폰 메모리가 모자란다
       'units': [{**r, 'hg': r['id'] in units} for r in sorted(V, key=lambda r: -r['a'])], 'geom_dir': 'data_v4/advisory/geom',
       'fronts_R2': fronts['R2_promo'], 'alt': alt, 'alt_cols': ['lab', 'a', 'mw', 'lo', 'd', 'lat', 'lon', 'f3', 'fab', 'fac', 'fbc'],
       'provenance': prov,
       'notes': {'mw': 'MW는 해당 면적에 0.045 kW/㎡를 곱한 참고 규모이며 실제 발전설비 용량이나 계통 접속 가능 용량을 의미하지 않습니다.',
                 'grid': '인근 분산전원 계통 여유 참고값(소재 읍면동 잔여 연계가능용량의 하한–상한). 실제 접속 가능 여부와 접속 용량은 별도 한전 검토가 필요합니다.',
                 'existing': '기존 태양광 시설 자료(위치를 확인할 수 있는 곳만)가 후보 공간 안에서 확인된 수. 확보한 공개 자료의 일부이며 전국 전수조사가 아닙니다 — 점이 없다고 시설이 없다는 뜻은 아닙니다.',
                 'unit': '후보 공간 = 21m 이내로 이어진 필지를 묶은 최소 공간 분석 단위(면적 하한 없음). 최종 사업 단위를 정하는 방법은 아직 정해지지 않았습니다.'}}
os.makedirs(os.path.join(OUT, 'advisory'), exist_ok=True)
gdir = os.path.join(OUT, 'advisory', 'geom'); os.makedirs(gdir, exist_ok=True)
for f_ in glob.glob(os.path.join(gdir, '*.json.gz')): os.remove(f_)
n_geo = 0
for sgg in labels:
    g_ = {str(r['id']): units[r['id']]['geometry'] for r in V if sgg in r['sggs'] and r['id'] in units}
    n_geo += len(g_)
    with gzip.open(os.path.join(gdir, f'{sgg}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump({'sgg': sgg, 'g': g_}, f, ensure_ascii=False, separators=(',', ':'))
cov_ = {int(k) for sgg in labels for k in json.load(gzip.open(os.path.join(gdir, f'{sgg}.json.gz'), 'rt', encoding='utf-8'))['g']}
assert cov_ == {r['id'] for r in V if r['id'] in units}, '[FAIL] 시군별 도형 파일이 도형 있는 후보 공간 전부를 담지 않음'
print(f"시군별 도형 파일 {len(labels)}개 · 도형 {n_geo:,}(시군 걸침은 시군마다 한 번) · {sum(os.path.getsize(os.path.join(gdir, x)) for x in os.listdir(gdir)) / 1e6:.2f} MB")
fo = os.path.join(OUT, 'advisory', 'gg_v1.json.gz')
with gzip.open(fo, 'wt', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
print(f"저장 {os.path.relpath(fo, SITE)} · {os.path.getsize(fo) / 1e6:.2f} MB · 사례 {len(cases)} · 읍면동 {len(emd)}")
print('요약', json.dumps({k: summary[k] for k in ('n_units', 'area_km2', 'bands', 'nondominated', 'geom', 'existing_in')}, ensure_ascii=False))
