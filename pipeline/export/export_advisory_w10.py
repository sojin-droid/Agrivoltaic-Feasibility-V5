# /// script
# requires-python = ">=3.9"
# dependencies = ["shapely>=2", "numpy"]
# ///
# -*- coding: utf-8 -*-
"""자문 화면용 '폭 10 m 미만 띠 제외' **잠정 근사** 자산 (PR-0047 · 사용자 결정 2026-10-14).

정본은 모델의 필지 단위 규칙(stages/v8_01_narrow_strip.py · narrow10 스위치)이고 데이터 PC 에서 돌아야 나온다.
그 전에 자문자가 띠가 빠진 모습을 볼 수 있도록, **발행된 후보 공간 도형**에 같은 뜻의 근사를 적용한다:
  ① 도형을 5 m 침식 → 5 m 팽창 (폭 10 m 미만 부분이 사라짐)
  ② 남은 조각을 21 m 규칙(10.5 m 버퍼 합집합)으로 다시 묶고, 원래 후보 안에서 **가장 큰 묶음**을 그 후보의 몸통으로 둔다
  ③ 면적 = 조각 도형 면적 × (장부면적 / 원 도형면적) — 장부 기준을 유지
필지 수는 다시 셀 수 없으므로(필지 경계가 발행 자산에 없음) 원 값을 그대로 둔다.

입력: data_v4/advisory/geom/{sgg}.json.gz (경기 자문 도형) · data_v4/units/{sgg}.json.gz (지역별 지도 시군)
산출: data_v4/advisory/w10/{sgg}.json.gz  {id: {a: 장부면적 근사(㎡), mw, parts: 조각 묶음 수, drop: 원래 대비 빠진 비율, g: GeoJSON geometry}}
      data_v4/advisory/w10_index.json     시군별 합계·생성 시각·규칙
사용: uv run pipeline/export/export_advisory_w10.py
"""
import glob, gzip, json, math, os, time
import numpy as np
import shapely
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely import transform as stf

SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(SITE, 'data_v4')
OUT = os.path.join(D, 'advisory', 'w10'); os.makedirs(OUT, exist_ok=True)
W, TAU, KW = 10.0, 21.0, 0.045
REGION_SGG = ['41220', '41590', '41500', '41480', '41670', '44180']   # advisory.html 지역별 지도(상위 3 + 파주·여주·보령)


def metric(g):
    lat = g.centroid.y; kx = 111320 * math.cos(math.radians(lat)); ky = 110540
    fwd = stf(g, lambda a: np.column_stack([a[:, 0] * kx, a[:, 1] * ky]))
    inv = lambda h: stf(h, lambda a: np.column_stack([a[:, 0] / kx, a[:, 1] / ky]))
    return fwd, inv


def w10(geom_json, a_ledger):
    g = shape(geom_json)
    if g.is_empty: return None
    gm, inv = metric(g); gm = gm.buffer(0); A = gm.area
    if A <= 0: return None
    o = gm.buffer(-W / 2, join_style=2).buffer(W / 2, join_style=2)
    pieces = [x for x in getattr(o, 'geoms', [o]) if not x.is_empty and x.area > 0]
    if not pieces:
        return {'a': 0, 'mw': 0, 'parts': 0, 'drop': 1.0, 'g': None}
    merged = unary_union([x.buffer(TAU / 2) for x in pieces])
    comps = list(getattr(merged, 'geoms', [merged]))
    best, best_pieces = 0, []
    for c in comps:
        ps = [x for x in pieces if x.intersects(c)]; a = sum(x.area for x in ps)
        if a > best: best, best_pieces = a, ps
    body = unary_union(best_pieces)
    if not body.is_valid:
        body = body.buffer(0)
    a_new = best * (a_ledger / A)
    gj = mapping(inv(body))
    # 좌표 자릿수 5 → 약 1 m (도형 파일과 같은 정밀도)
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
    gj = {'type': gj['type'], 'coordinates': rnd(gj['coordinates'])}
    return {'a': int(round(a_new)), 'mw': round(a_new * KW / 1000, 1), 'parts': len(comps), 'drop': round(1 - best / A, 3), 'g': gj}


index = {'generated': time.strftime('%Y-%m-%d %H:%M'), 'rule': f'잠정 근사 — 후보 도형 {W:g} m 침식·팽창(폭 {W:g} m 미만 띠 제거) → 조각을 {TAU:g} m 로 재묶음 → 가장 큰 묶음 · 면적은 장부면적 비례. 정본은 모델 필지 단위 narrow10(PR-0047)',
         'w_m': W, 'sgg': {}}
# ① 경기 자문 도형
gg = json.load(gzip.open(os.path.join(D, 'advisory', 'gg_v1.json.gz'), 'rt', encoding='utf-8'))
AREA = {u['id']: u['a'] for u in gg['units']}
done = {}
for fp in sorted(glob.glob(os.path.join(D, 'advisory', 'geom', '*.json.gz'))):
    sgg = os.path.basename(fp).split('.')[0]
    G = json.load(gzip.open(fp, 'rt', encoding='utf-8'))['g']
    out = {}
    for k, gj in G.items():
        try:
            r = w10(gj, AREA.get(int(k), 0))
        except Exception as e:   # 드물게 유효하지 않은 도형 — 원 값 유지(띠 제외 없음)로 둔다
            r = {'a': AREA.get(int(k), 0), 'mw': round(AREA.get(int(k), 0) * KW / 1000, 1), 'parts': 1, 'drop': 0.0, 'g': None, 'err': type(e).__name__}
        if r: out[k] = r
    done[sgg] = out
# ② 지역별 지도 시군(units) — 경기 밖(보령)과 경기 시군의 units 도형(지역별 지도가 쓰는 파일)
for sgg in REGION_SGG:
    fp = os.path.join(D, 'units', f'{sgg}.json.gz')
    if not os.path.exists(fp): continue
    out = done.setdefault(sgg, {})
    for ft in json.load(gzip.open(fp, 'rt', encoding='utf-8'))['features']:
        p = ft['properties']; k = str(p['id'])
        if k in out or p.get('t') == 'quality_review': continue
        try:
            r = w10(ft['geometry'], p['a'])
        except Exception as e:
            r = {'a': p['a'], 'mw': p['mw'], 'parts': 1, 'drop': 0.0, 'g': None, 'err': type(e).__name__}
        if r: out[k] = r
for sgg, out in done.items():
    with gzip.open(os.path.join(OUT, f'{sgg}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    tot_a = sum(v['a'] for v in out.values()); orig = sum(AREA.get(int(k), 0) for k in out)
    index['sgg'][sgg] = {'n': len(out), 'a_w10': tot_a, 'n_split': sum(1 for v in out.values() if v['parts'] > 1), 'n_gone': sum(1 for v in out.values() if v['a'] == 0)}
    print(f"{sgg}: {len(out):,}곳 · 쪼개짐 {index['sgg'][sgg]['n_split']:,} · 사라짐 {index['sgg'][sgg]['n_gone']:,}", flush=True)
json.dump(index, open(os.path.join(D, 'advisory', 'w10_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('완료', len(done), '시군 →', OUT)
