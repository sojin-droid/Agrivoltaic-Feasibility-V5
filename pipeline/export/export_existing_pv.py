# /// script
# requires-python = ">=3.9"
# dependencies = ["shapely>=2", "requests"]
# ///
# -*- coding: utf-8 -*-
"""기존 태양광 시설 — 원천 전량(collect_existing_pv.py 가 받은 15107742) → data_v4/existing_pv_v4.json.gz.

2026-10-13 교체: 종전(ADR-0053)은 위치 독립 검증 VALID 만 지도에 찍어 135개 시군(당진 등)이 0곳이었다.
이제 좌표를 확인할 수 있는 시설은 모두 찍고, 위치를 얼마나 믿을 수 있는지를 등급으로 함께 싣는다.
  등급(pts[8])  v = 원천 좌표가 주소의 읍면동 안에 있음(위치 확인)
               c = 원천 좌표가 있으나 주소의 읍면동과 다름(좌표 참고)
               g = 원천 좌표가 없어 지번 주소로 찾은 위치(VWorld 주소 검색 · 필지 위치)
  종류(pts[3])  y = 영농형(시설 이름에 '영농') · f = 수상(설치 위치 또는 이름에 '수상') · p = 그 밖의 태양광
시군은 원천 지번 주소(시도·시군구)로 붙인다 — 경계 자료의 신 코드(광주·전남 12xxx)와 사이트 시군 코드(46xxx·29xxx)가 달라서.
  pts: [lon, lat, kw|null, type, status, src, sgg5, emd8|null, grade]   (시설 이름은 싣지 않는다 — 개인 이름이 섞여 있음)
사용: uv run pipeline/export/export_existing_pv.py      (VWORLD_API_KEY 가 있으면 좌표 없는 시설을 주소로 찾는다 · 결과는 캐시)
"""
import datetime, glob, gzip, json, os, re, sys, time
from collections import Counter
import requests
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(SITE, 'data_v4')
ROOT = os.environ.get('AGRI_ROOT') or os.path.expanduser('~/Developer/agri-data')
RAW = sorted(glob.glob(os.path.join(ROOT, 'raw', 'existing_pv', 'std_15107742', '2*')))
if not RAW:
    sys.exit('원천이 없습니다 — 먼저 uv run pipeline/collect/collect_existing_pv.py')
RAWDIR = RAW[-1]
MAN = json.load(open(os.path.join(RAWDIR, 'manifest.json'), encoding='utf-8'))
VK = os.environ.get('VWORLD_API_KEY')
GEOCACHE = os.path.join(ROOT, 'cache', 'vworld_geocode_parcel.json')

# ── 원천 읽기 (필드 이름 대소문자·밑줄 차이 흡수) ──
def norm(d):
    return {re.sub(r'[^a-z0-9]', '', k.lower()): v for k, v in d.items()}

rows = []
for fp in sorted(glob.glob(os.path.join(RAWDIR, 'page_*.json'))):
    b = json.load(open(fp, encoding='utf-8')).get('response', {}).get('body', {}) or {}
    it = b.get('items') or []
    if isinstance(it, dict):
        it = it.get('item') or []
    if isinstance(it, dict):
        it = [it]
    rows += [norm(r) for r in it]
print(f"원천 {len(rows):,}행 ({os.path.basename(RAWDIR)} · manifest {MAN['total_count']:,})")
if len(rows) != MAN['rows_saved']:
    sys.exit('저장된 페이지 행 수가 manifest 와 다르다 — 수집을 다시 돌릴 것')

def g(r, *ks):
    for k in ks:
        v = r.get(k)
        if v not in (None, ''):
            return str(v).strip()
    return ''

def num(s):
    try:
        return float(re.sub(r'[^0-9.\-]', '', s)) if s else None
    except ValueError:
        return None

# ── 시군: 지번(없으면 도로명) 주소 → 사이트 시군 코드 ──
SIDO = {'서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구', '인천광역시': '인천', '광주광역시': '광주', '대전광역시': '대전',
        '울산광역시': '울산', '세종특별자치시': '세종', '경기도': '경기', '강원도': '강원', '강원특별자치도': '강원', '충청북도': '충북',
        '충청남도': '충남', '전라북도': '전북', '전북특별자치도': '전북', '전라남도': '전남', '경상북도': '경북', '경상남도': '경남',
        '제주특별자치도': '제주', '전남광주통합특별시': '전남광주'}
SGG = {v['name']: k for k, v in json.load(open(os.path.join(DATA, 'sgg_matrix.json'), encoding='utf-8'))['codes'].items()}
BY_TAIL = {}
for nm, code in SGG.items():
    BY_TAIL.setdefault(nm.split(' ', 1)[1], []).append((nm.split(' ', 1)[0], code))

def sgg_of(addr):
    t = addr.split()
    if not t:
        return None
    sd = SIDO.get(t[0], t[0][:2])
    if sd == '세종':
        return SGG.get('세종 세종시')
    cands = []
    if len(t) > 2 and t[1].endswith('시') and t[2].endswith('구'):
        cands.append(t[1] + t[2])
    if len(t) > 1:
        cands.append(t[1])
    for c in cands:
        if sd != '전남광주' and f'{sd} {c}' in SGG:
            return SGG[f'{sd} {c}']
        ok = [code for s, code in BY_TAIL.get(c, []) if (s in ('전남', '광주') if sd == '전남광주' else True)]
        if len(ok) == 1:                       # 시도가 바뀐 경우(군위군 → 대구 등) — 이름이 하나뿐일 때만
            return ok[0]
    return None

def emd_name_of(addr):
    for tok in addr.split()[1:5]:
        if re.search(r'(읍|면|동|가)$', tok) and not re.search(r'(시|군|구)$', tok):
            return tok
    return None

# ── 읍면동 경계(사이트 자산) — 좌표가 주소의 읍면동 안에 있는지 ──
E = json.load(gzip.open(os.path.join(DATA, 'grid_emd.json.gz'), 'rt', encoding='utf-8'))['features']
POLY = [shape(f['geometry']) for f in E]
TREE = STRtree(POLY)
def emd_at(lon, lat):
    p = Point(lon, lat)
    for i in TREE.query(p):
        if POLY[i].contains(p):
            return E[i]['properties']['c'], E[i]['properties']['n']
    return None, None

# ── 좌표 없는 시설: 지번 주소로 VWorld 주소 검색(필지) ──
geo = json.load(open(GEOCACHE, encoding='utf-8')) if os.path.exists(GEOCACHE) else {}
S = requests.Session()
def geocode(addr):
    if addr in geo:
        return geo[addr]
    if not VK:
        return None
    try:
        r = S.get('https://api.vworld.kr/req/address', params={'service': 'address', 'request': 'getcoord', 'version': '2.0', 'crs': 'epsg:4326',
                  'address': addr, 'refine': 'true', 'simple': 'true', 'format': 'json', 'type': 'parcel', 'key': VK}, timeout=20).json()
        res = r.get('response', {})
        pt = res.get('result', {}).get('point') if res.get('status') == 'OK' else None
        geo[addr] = [round(float(pt['x']), 6), round(float(pt['y']), 6)] if pt else False
    except Exception:
        return None                              # 일시 오류는 캐시하지 않는다
    time.sleep(0.05)
    return geo[addr]

ST = [(r'폐기|폐업|취소|철거', 'closed'), (r'중단|휴지', 'stop'), (r'정상|가동|운영|개시', 'op')]   # '가동중단' 이 '가동' 에 먼저 걸리지 않게 — 중단·폐기를 먼저 본다
def status(s):
    for pat, code in ST:
        if s and re.search(pat, s):
            return code
    return 'other' if s else 'unk'

pts, by, seen, unmatched = [], {}, set(), Counter()
for r in rows:
    name = g(r, 'solargenfcltnm')
    lot, road = g(r, 'lctnlotnoaddr'), g(r, 'lctnroadnmaddr')
    addr = lot or road
    sgg = sgg_of(addr)
    if not sgg:
        unmatched[(addr.split() or ['(주소 없음)'])[0]] += 1
        continue
    kw = num(g(r, 'capa'))
    pos = g(r, 'instldtlpstnsenm')
    typ = 'y' if '영농' in name else 'f' if ('수상' in pos or '수상' in name or '수면' in pos) else 'p'
    st = status(g(r, 'oprtngsttssenm'))
    lat, lon = num(g(r, 'latitude')), num(g(r, 'longitude'))
    if lat and lon and lat > 90 and lon < 90:
        lat, lon = lon, lat                      # 위도·경도 뒤바뀐 행
    s = by.setdefault(sgg, {'n': 0, 'valid': 0, 'cond': 0, 'geo': 0, 'nolocstatus': 0, 'yeongnong': 0, 'floating': 0, 'kw_known': 0})
    key = (name, addr, kw)
    if key in seen:                               # 같은 시설이 두 번 실린 행
        continue
    seen.add(key)
    s['n'] += 1
    s['yeongnong'] += typ == 'y'
    s['floating'] += typ == 'f'
    s['kw_known'] += kw is not None
    grade = None
    if lat and lon and 33 < lat < 39 and 124 < lon < 132:
        code, en = emd_at(lon, lat)
        want = emd_name_of(lot) if lot else emd_name_of(road)
        grade = 'v' if (en and want and en == want) else 'c'
    elif lot:
        gp = geocode(lot)
        if gp:
            lon, lat = gp
            code, en = emd_at(lon, lat)
            grade = 'g'
    if not grade:
        s['nolocstatus'] += 1
        continue
    s[{'v': 'valid', 'c': 'cond', 'g': 'geo'}[grade]] += 1
    pts.append([round(lon, 5), round(lat, 5), None if kw is None else round(kw), typ, st, 'std_15107742', sgg, code, grade])

if VK:
    os.makedirs(os.path.dirname(GEOCACHE), exist_ok=True)
    json.dump(geo, open(GEOCACHE, 'w', encoding='utf-8'), ensure_ascii=False)
ty = Counter(p[3] for p in pts)
meta = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'n_records': sum(v['n'] for v in by.values()), 'n_yeongnong_records': sum(v['yeongnong'] for v in by.values()),
        'n_floating_records': sum(v['floating'] for v in by.values()), 'n_sources': 1, 'sources': ['std_15107742'],
        'retrieved_at': MAN['retrieved_at'], 'n_points': len(pts), 'grades': dict(Counter(p[8] for p in pts)),
        'rule': '좌표를 확인할 수 있는 시설은 모두 표시 — 등급 v(원천 좌표가 주소 읍면동 안) · c(원천 좌표, 주소 읍면동과 다름) · g(좌표 없어 지번 주소로 찾은 필지 위치). 점은 허가 자료의 위치이며 패널의 실제 자리가 아닐 수 있다.',
        'coverage_note': '공공데이터포털 「전국태양광발전소전기사업허가정보표준데이터」(지자체 발전사업 허가 대장) 전량 — 전국 기존 설비 전수가 아니다(허가 대장에 없는 시설·미제공 지자체는 빠진다). 영농형은 시설 이름에 "영농"이, 수상은 설치 위치나 이름에 "수상"이 적힌 경우만 구분한다.',
        'status_codes': {'op': '가동·개시', 'stop': '가동중단', 'closed': '폐기·폐업·취소', 'other': '허가·공사 등', 'unk': '원천에 상태 없음'},
        'type_codes': {'p': '태양광', 'y': '영농형', 'f': '수상'},
        'grade_codes': {'v': '위치 확인', 'c': '좌표 참고(주소 읍면동과 다름)', 'g': '주소로 찾은 위치'}}
codes = {p[7] for p in pts if p[7]}   # 지도 표지에 소재 읍면동 이름을 적기 위함
meta['emd_names'] = {f['properties']['c']: f['properties']['n'] for f in E if f['properties']['c'] in codes}
with gzip.open(os.path.join(DATA, 'existing_pv_v4.json.gz'), 'wt', encoding='utf-8') as fo:
    json.dump({'meta': meta, 'pts': pts, 'by_sgg': by}, fo, ensure_ascii=False, separators=(',', ':'))
print(f"existing_pv_v4: 점 {len(pts):,} (등급 {meta['grades']}) · 종류 {dict(ty)} · 시군 {len(by)} · 시군 미매칭 {sum(unmatched.values()):,} {unmatched.most_common(5)}")
