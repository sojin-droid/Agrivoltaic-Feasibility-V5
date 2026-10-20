# -*- coding: utf-8 -*-
"""자문 화면 '위성영상 검토 — 실제 설치 가능 공간' 자산 — data_v4/advisory/nonfarm_examples_v1.json (2026-10-20).

비농지 제외(ADR-0060) 전·후를 같은 기준으로 견준다.
  · 전(지목상) = 비농지 제외를 넣기 직전 발행본의 후보 공간(BEFORE 커밋의 data_v4/units/{sgg}.json.gz) — 장부 지목이 농지인 필지만으로 묶은 값
  · 후(실제 설치 가능) = 지금 data_v4/units/{sgg}.json.gz — 위성영상 검토·자동 제외(도로·건물·띠)를 거친 값
대표 사례 3곳은 사용자가 제외를 판단할 때 쓴 검토 화면(2026-10-15 3MW 이상 위성 감사 page24)의 후보다.
사례의 '실제 설치 가능' = 전 도형과 겹치는 후 후보 공간 도형의 넓이(EPSG:5179). 판정 코드·메모는 감사 CSV 그대로.
시군 합계 = 1MW(22,222㎡)·3MW(66,667㎡) 이상 후보 공간의 수와 면적(시군 파일 안에서 id 중복 제거, 경기는 41* 전체에서 중복 제거).
새 판정·새 점수 없음. 값은 발행 자산에서만 읽는다.
사용: python pipeline/export/export_advisory_nonfarm_v1.py   (shapely · pyproj 필요, git 이력에서 BEFORE 를 읽는다)
"""
import os, sys, json, gzip, glob, subprocess, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree
from shapely import transform as shp_transform
from pyproj import Transformer
import numpy as np

BEFORE = 'bebc9b43'          # ADR-0060 (6d8129c9) 직전 발행본
KW = 0.045
SGGS = ['41220', '41590', '41500', '41480', '41670', '44180']
# (시군, 검토 화면의 후보 번호, 결과 구분, 감사 판정 코드, 감사 메모, 검토 화면 이미지)
EXAMPLES = [
    ('44180', 3681887, 'keep', 'OK', '보령 웅천 — 간척 논. 비농지 없음', 'assets/advisory/nonfarm/44180_3681887.jpg'),
    ('41590', 1938290, 'partial', 'MIX', '화성 장안 — 논 + 축사·비닐하우스 섞임(일부 농지)', 'assets/advisory/nonfarm/41590_1938290.jpg'),
    ('41220', 1037963, 'drop', 'BLD', '평택 서탄 — 기지 옆 나대지·군 시설(건물 다수) 위', 'assets/advisory/nonfarm/41220_1037963.jpg'),
]
to5179 = Transformer.from_crs(4326, 5179, always_xy=True)
prj = lambda g: shp_transform(g, lambda c: np.column_stack(to5179.transform(c[:, 0], c[:, 1])))   # 넓이는 EPSG:5179 ㎡


def old_units(path):
    raw = subprocess.check_output(['git', '-C', SITE, 'show', f'{BEFORE}:{path}'])
    return json.loads(gzip.decompress(raw))


def new_units(sgg):
    return json.load(gzip.open(os.path.join(OUT, 'units', f'{sgg}.json.gz'), 'rt', encoding='utf-8'))


def stats(props):
    b1 = [p for p in props if p['a'] >= 22222]; b3 = [p for p in props if p['a'] >= 66667]
    km = lambda L: round(sum(p['a'] for p in L) / 1e6, 2)
    return {'n1': len(b1), 'km2_1': km(b1), 'mw1': round(km(b1) * 1e6 * KW / 1000, 1), 'n3': len(b3), 'km2_3': km(b3), 'mw3': round(km(b3) * 1e6 * KW / 1000, 1)}


def dedup(fcs):
    d = {}
    for fc in fcs:
        for f in fc['features']:
            d[f['properties']['id']] = f['properties']
    return list(d.values())


totals = {}
for s in SGGS:
    totals[s] = {'before': stats(dedup([old_units(f'data_v4/units/{s}.json.gz')])), 'after': stats(dedup([new_units(s)]))}
old_files = [p for p in subprocess.check_output(['git', '-C', SITE, 'ls-tree', '--name-only', BEFORE, 'data_v4/units/']).decode().split() if os.path.basename(p).startswith('41')]
totals['41'] = {'before': stats(dedup([old_units(p) for p in old_files])),
                'after': stats(dedup([json.load(gzip.open(p, 'rt', encoding='utf-8')) for p in sorted(glob.glob(os.path.join(OUT, 'units', '41*.json.gz')))]))}

examples = []
for s, oid, kind, code, note, img in EXAMPLES:
    of = next(f for f in old_units(f'data_v4/units/{s}.json.gz')['features'] if f['properties']['id'] == oid)
    og = shape(of['geometry']).buffer(0); og_m = prj(og)
    nf = new_units(s)['features']; ng = [prj(shape(f['geometry']).buffer(0)) for f in nf]; tree = STRtree(ng)
    hits = [(j, ng[j].intersection(og_m).area) for j in tree.query(og_m) if ng[j].intersects(og_m)]
    hits = [(j, a) for j, a in hits if a > 1]
    keep = sum(a for _, a in hits)
    examples.append({'sgg': s, 'id_before': oid, 'kind': kind, 'code': code, 'note': note, 'image': img,
                     'before': {'a': of['properties']['a'], 'mw': of['properties']['mw'], 'n': of['properties']['n'], 'geom_m2': round(og_m.area)},
                     'after': {'a': round(keep), 'mw': round(keep * KW / 1000, 1), 'share': round(keep / og_m.area, 3) if og_m.area else 0,
                               'ids': [nf[j]['properties']['id'] for j, _ in sorted(hits, key=lambda x: -x[1])]},
                     'geom_before': mapping(og.simplify(0.00002))})
    print(s, oid, kind, 'before', of['properties']['a'], 'after', round(keep), f"{keep / og_m.area * 100:.0f}%")

out = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'before_commit': BEFORE, 'kw_per_m2': KW,
       'rule': {'before': '지목상 — 장부 지목이 농지인 필지로 묶은 후보 공간(비농지 제외 전 발행본)',
                'after': '실제 설치 가능 — 위성영상 검토와 자동 제외(도로·건물·폭 10 m 미만 띠)로 비농지를 뺀 뒤 남은 후보 공간',
                'example_after': '검토 전 후보 자리와 겹치는 검토 후 후보 공간 도형의 넓이',
                'totals': '1MW(22,222㎡)·3MW(66,667㎡) 이상으로 남은 후보 공간의 수와 면적 · MW = 면적 × 0.045 kW/㎡'},
       'review': {'image_source': '2026-10-15 3MW 이상 위성 육안 감사 화면(Esri World Imagery) — 판정 근거로 쓴 화면 그대로(머리글 띠만 잘라냄)',
                  'audit_csv': 'agrivoltaic-model model/data/visual_audit/sat_audit_3mw_2026-10-15.csv'},
       'examples': examples, 'totals': totals}
os.makedirs(os.path.join(OUT, 'advisory'), exist_ok=True)
json.dump(out, open(os.path.join(OUT, 'advisory', 'nonfarm_examples_v1.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('nonfarm_examples_v1:', len(examples), 'examples ·', len(totals), 'totals')
