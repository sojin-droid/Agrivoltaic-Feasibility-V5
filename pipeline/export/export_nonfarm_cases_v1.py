# -*- coding: utf-8 -*-
"""'제외 사례' 탭(nonfarm_cases.html) 자산 — 비농지 제외(ADR-0060) 유형별 전·후 비교 (2026-10-20).

사례: 2026-10-15 위성 육안 감사(agrivoltaic-model model/data/visual_audit/sat_audit_3mw_2026-10-15.csv)의 판정 코드별로,
      감사 판정과 최종(필지 단위) 결과가 같은 방향인 후보만 골랐다(제외 유형은 남은 비율 25% 이하, 섞임은 40–90%).
전(지목상) = 비농지 제외 직전 발행본(BEFORE 커밋)의 후보 공간 도형 · 후(실제 설치 가능) = 지금 data_v4/units 의 후보 공간 중 전 도형과 겹치는 것.
이미지(Esri World Imagery 위에 그림 · Chrome 헤드리스로 찍음):
  {key}_a.jpg  전 — 노란 선 = 지목상 후보 자리
  {key}_b.jpg  후 — 파란 면 = 남은 설치 가능 공간 · 노란 점선 = 전 자리 (a 와 같은 범위)
  {key}_c.jpg  확대 — 가장 크게 빠진 곳 중심 z17–18
값: data_v4/nonfarm_cases_v1.json. 새 판정 없음.
사용: python pipeline/export/export_nonfarm_cases_v1.py   (shapely · pyproj · numpy · playwright, Chrome 설치 필요, git 이력에서 BEFORE 를 읽는다)
"""
import os, sys, json, gzip, subprocess, datetime, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT
import numpy as np
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely import transform as shp_transform
from pyproj import Transformer

BEFORE = 'bebc9b43'
KW = 0.045
IMG = os.path.join(SITE, 'assets', 'nonfarm_cases')
TYPES = [('road', '도로 부지 · 농로 띠', '지목은 논·밭이지만 실제로는 도로·농로·제방 위를 따라 길게 이어진 필지. 도로 중심선(표준노드링크·OSM)과 위성사진으로 확인해 뺐습니다.'),
         ('bld', '건물 · 시설 · 공사 부지', '군사시설·원전·공장·공사장처럼 건물이나 포장면이 들어선 필지. GIS건물통합정보와 위성사진으로 확인해 뺐습니다.'),
         ('barn', '축사', '논밭 사이에 들어선 축사(가축 사육 시설) 필지. 건물이라 뺐고, 둘레의 논은 그대로 남겼습니다.'),
         ('for', '산림 · 임야화', '지목은 농지지만 오래 경작하지 않아 숲이 된 산지 필지. 위성사진으로 확인해 뺐습니다.'),
         ('wat', '하천 둔치 · 강둑 · 수면', '강변 둔치·제방·수로처럼 물가에 놓인 필지. 홍수 때 잠기거나 하천 시설이라 설치 대상이 아닙니다.'),
         ('mix', '일부만 비농지 (섞임)', '논밭 사이에 축사·공장 같은 건물이 섞인 곳. 건물 필지만 빼고 논밭은 남겼습니다. 비닐하우스는 빼는 대상이 아니라, 하우스형 영농형 태양광 후보 위치로 따로 모읍니다.')]
# (유형, 시군, 감사 당시 후보 번호)
CASES = [('road', '41500', 1543370), ('road', '41220', 1016949), ('road', '44200', 3773269), ('road', '44270', 4165239),
         ('bld', '41220', 1037963), ('bld', '41220', 1038571), ('bld', '41590', 1829078), ('bld', '47930', 10147157),
         # 김해 #10657762 는 뺐다(2026-10-20 사용자 검토 — 휴경지를 공사부지로 잘못 제외, 비닐하우스·왼쪽 위는 남김 → 정정 대기)
         ('for', '51780', 13055015), ('for', '51730', 12769790),
         ('wat', '41670', 2170137), ('wat', '27710', 247488), ('wat', '48270', 10704190),
         ('barn', '41590', 1938290), ('mix', '41220', 1045513)]
# 영주 #8571886 는 뺐다(2026-10-20 사용자 검토 — 산림으로 뺀 땅이 논, 정정 대기) · 화성 #1938290 은 '축사'로 분류(사용자)
# 서천 #4501952 는 뺐다(2026-10-20 사용자 검토 — 빠진 땅이 모두 휴경지, 정정 대기)
to5179 = Transformer.from_crs(4326, 5179, always_xy=True)
to4326 = Transformer.from_crs(5179, 4326, always_xy=True)
prj = lambda g: shp_transform(g, lambda c: np.column_stack(to5179.transform(c[:, 0], c[:, 1])))


def old_fc(s):
    return json.loads(gzip.decompress(subprocess.check_output(['git', '-C', SITE, 'show', f'{BEFORE}:data_v4/units/{s}.json.gz'])))


def new_fc(s):
    return json.load(gzip.open(os.path.join(OUT, 'units', f'{s}.json.gz'), 'rt', encoding='utf-8'))


names = {k: v.get('name', k) for k, v in json.load(open(os.path.join(OUT, 'sgg_matrix.json'), encoding='utf-8'))['codes'].items()}
cases, cache = [], {}
for t, s, oid in CASES:
    if s not in cache:
        cache[s] = (old_fc(s), new_fc(s))
    O, N = cache[s]
    of = next((f for f in O['features'] if f['properties']['id'] == oid), None)
    if of is None:
        print('없음', s, oid); continue
    og = shape(of['geometry']).buffer(0); ogm = prj(og)
    nf = N['features']; ng = [prj(shape(f['geometry']).buffer(0)) for f in nf]; tree = STRtree(ng)
    hit = [j for j in tree.query(ogm) if ng[j].intersects(ogm) and ng[j].intersection(ogm).area > 1]
    keep = unary_union([ng[j].intersection(ogm) for j in hit]) if hit else None
    keep_a = keep.area if keep is not None else 0.0
    gone = ogm.difference(keep) if keep is not None else ogm
    parts = sorted(getattr(gone, 'geoms', [gone]), key=lambda g: -g.area)
    cx, cy = parts[0].representative_point().coords[0] if parts and not parts[0].is_empty else ogm.representative_point().coords[0]
    lon, lat = to4326.transform(cx, cy)
    key = f'{s}_{oid}'
    cases.append({'key': key, 'type': t, 'sgg': s, 'sgg_name': names.get(s, s), 'id_before': oid,
                  'before': {'a': of['properties']['a'], 'mw': of['properties']['mw'], 'n': of['properties']['n']},
                  'after': {'a': round(keep_a), 'mw': round(keep_a * KW / 1000, 1), 'share': round(keep_a / ogm.area, 3), 'ids': [nf[j]['properties']['id'] for j in hit]},
                  'detail': {'lat': round(lat, 6), 'lon': round(lon, 6), 'zoom': 18 if ogm.area < 150000 else 17},
                  'img': {k: f'assets/nonfarm_cases/{key}_{k}.jpg' for k in 'abc'},
                  '_geom_before': mapping(og), '_geom_after': [nf[j]['geometry'] for j in hit]})
    print(t, key, f"{keep_a / ogm.area * 100:.0f}%")

# ── 이미지 — Leaflet 한 장(1100×720)에 전/후/확대를 차례로 그려 찍는다 ──
PAGE = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><style>html,body,#m{margin:0;width:1100px;height:720px}</style></head>
<body><div id="m"></div><script>
const m = L.map('m', {zoomControl: false, attributionControl: true, fadeAnimation: false, zoomAnimation: false, zoomSnap: 0.25});
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, maxNativeZoom: 18, attribution: '© Esri'}).addTo(m);
let lay = L.layerGroup().addTo(m);
window.draw = (mode, B, A, d) => { lay.clearLayers();
  const b = L.geoJSON(B, {style: mode === 'a' ? {color: '#FFE14D', weight: 3, fill: false} : {color: '#FFE14D', weight: 2, dashArray: '6 5', fill: false}}).addTo(lay);
  if (mode !== 'a') L.geoJSON({type: 'FeatureCollection', features: A.map(g => ({type: 'Feature', geometry: g, properties: {}}))}, {style: {color: '#2a6fe0', weight: 2, fillColor: '#3d8bff', fillOpacity: .5}}).addTo(lay);
  if (mode === 'c') m.setView([d.lat, d.lon], d.zoom); else m.fitBounds(b.getBounds(), {padding: [16, 16], maxZoom: 18}); };
window.tilesDone = () => { const t = [...document.querySelectorAll('img.leaflet-tile')]; return t.length > 0 && t.every(i => i.complete && i.naturalWidth > 0); };
</script></body></html>"""


async def shoot():
    from playwright.async_api import async_playwright
    os.makedirs(IMG, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        pg = await b.new_page(viewport={'width': 1100, 'height': 720}, device_scale_factor=1.5)
        await pg.set_content(PAGE); await pg.wait_for_function('!!(window.L && window.draw)')
        for c in cases:
            for mode in 'abc':
                await pg.evaluate('([m,B,A,d]) => draw(m,B,A,d)', [mode, c['_geom_before'], c['_geom_after'], c['detail']])
                for _ in range(60):
                    await pg.wait_for_timeout(400)
                    if await pg.evaluate('tilesDone()'):
                        break
                await pg.wait_for_timeout(800)
                await pg.screenshot(path=os.path.join(SITE, c['img'][mode]), type='jpeg', quality=78)
            print('찍음', c['key'])
        await b.close()

asyncio.run(shoot())
for c in cases:
    c.pop('_geom_before'); c.pop('_geom_after')
json.dump({'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'before_commit': BEFORE, 'kw_per_m2': KW,
           'types': [{'key': k, 'label': l, 'desc': d} for k, l, d in TYPES], 'cases': cases,
           'rule': '지목 대비 실제 설치 가능 = 남은 설치 가능 면적 ÷ 지목상 후보 면적(도형 넓이 · EPSG:5179) · MW = 면적 × 0.045 kW/㎡',
           'source': '사례 선정: 2026-10-15 위성 육안 감사 판정 · 전후 값: 비농지 제외 전 발행본(' + BEFORE + ')과 현재 발행본 비교 · 영상: Esri World Imagery'},
          open(os.path.join(OUT, 'nonfarm_cases_v1.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('nonfarm_cases_v1:', len(cases))
