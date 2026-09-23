# -*- coding: utf-8 -*-
"""기존 태양광 시설(위치 검증 VALID 만) · 시군별 품질 집계 · provenance 기준일 export (V5.5 · GGI 검토 §21·§22·§23).

ADR-0053: 공간 표시는 spatial_attribution_status = VALID 만. CONDITIONAL·UNVERIFIED·UNKNOWN 은 **건수로만** 병기(보조 표기).
  existing_pv_v4.json.gz  { pts: [[lon, lat, kw|null, type, status_code, src]] (VALID · 좌표 EPSG:5186 → WGS84) ,
                            by_sgg: { sgg5: {n, valid, cond, unver, unk, yeongnong, kw_known} } , meta }
  provenance_v4.json      provenance_v1 의 dataset 단위 수집일·원천 판·완전성 판정 — 화면의 "자료 기준일" 은 이 값만 쓴다(추정 금지).
전수 조사가 아니다 — existing_pv_v1 은 확보된 공개 자료(KPX·허가 대장·시도 공개분)의 합이며 전국 기존 설비 전수가 아니다(ADR-0051 L9).
사용: python pipeline/export/export_existing_v4.py
"""
import os, sys, json, gzip, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import duckdb
from pyproj import Transformer

DB = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
con = duckdb.connect(DB, read_only=True)
T = Transformer.from_crs(5186, 4326, always_xy=True)

valid = con.execute("""SELECT e.x, e.y, e.capacity_kw, e.pv_type, e.status, e.src, e.sgg5
                       FROM spatial_attribution_v1 s JOIN existing_pv_v1 e ON e.site_id = s.entity_id
                       WHERE s.spatial_attribution_status = 'VALID' AND e.x IS NOT NULL AND e.y IS NOT NULL""").fetchall()
ST = {'정상가동': 'op', '정상운영': 'op', '사업개시': 'op', '가동중단': 'stop', '폐기': 'closed', '폐업': 'closed', '인허가취소': 'closed'}
pts = []
for x, y, kw, t, st, src, sgg in valid:
    lon, lat = T.transform(float(x), float(y))
    pts.append([round(lon, 5), round(lat, 5), (None if kw is None else round(float(kw))), ('y' if t == '영농형' else 'u' if t == 'unknown' else 'p'), ST.get(st, 'other' if st and st != 'not_in_source' else 'unk'), src, sgg])
by = {}
for sgg, n, v, c, u, k, yn, kwk in con.execute("""
    SELECT e.sgg5, COUNT(*), COUNT(*) FILTER (s.spatial_attribution_status='VALID'), COUNT(*) FILTER (s.spatial_attribution_status='CONDITIONAL'),
           COUNT(*) FILTER (s.spatial_attribution_status='UNVERIFIED'), COUNT(*) FILTER (s.spatial_attribution_status='UNKNOWN'),
           COUNT(*) FILTER (e.pv_type='영농형'), COUNT(*) FILTER (e.capacity_kw IS NOT NULL)
    FROM existing_pv_v1 e LEFT JOIN spatial_attribution_v1 s ON s.entity_id = e.site_id
    WHERE e.sgg5 IS NOT NULL AND e.dedup_status NOT LIKE 'duplicate_of:%' GROUP BY e.sgg5""").fetchall():
    by[sgg] = {'n': n, 'valid': v, 'cond': c, 'unver': u, 'unk': k, 'nolocstatus': n - v - c - u - k, 'yeongnong': yn, 'kw_known': kwk}
tot = con.execute("SELECT COUNT(*), COUNT(*) FILTER (pv_type='영농형'), COUNT(DISTINCT src) FROM existing_pv_v1 WHERE dedup_status NOT LIKE 'duplicate_of:%'").fetchone()
srcs = [r[0] for r in con.execute("SELECT DISTINCT src FROM existing_pv_v1 ORDER BY 1").fetchall()]
meta = {'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'n_records': tot[0], 'n_yeongnong_records': tot[1], 'n_sources': tot[2], 'sources': srcs,
        'n_valid_points': len(pts), 'rule': 'ADR-0053 — 지도 표시는 spatial_attribution_status=VALID 만(원 좌표 + 행 단위 독립 검증 ≤100 m + 읍면동 일치). 나머지 등급은 건수만.',
        'coverage_note': '전국 기존 설비 전수가 아니다 — KPX·발전사업 허가 대장·시도 공개분의 합(ADR-0051 L9). 영농형 구분은 원천 표기가 있는 행만.',
        'status_codes': {'op': '가동·개시', 'stop': '가동중단', 'closed': '폐기·폐업·취소', 'other': '허가·공사 등', 'unk': '원천에 상태 없음'},
        'type_codes': {'p': '태양광', 'y': '영농형', 'u': '미상'}}
with gzip.open(os.path.join(SITE, 'data_v4', 'existing_pv_v4.json.gz'), 'wt', encoding='utf-8') as fo:
    json.dump({'meta': meta, 'pts': pts, 'by_sgg': by}, fo, ensure_ascii=False, separators=(',', ':'))
print(f"existing_pv_v4: VALID 점 {len(pts):,} · 시군 집계 {len(by)} · 원천 {tot[2]} · 총 {tot[0]:,}행(영농형 표기 {tot[1]})")

prov = con.execute("""SELECT dataset_id, kind, provider, source_name, collection_date, collection_date_basis, original_source_version,
                             internal_snapshot_version, provenance_status, layer, is_canon FROM provenance_v1 ORDER BY dataset_id""").fetchall()
cols = ['dataset_id', 'kind', 'provider', 'source_name', 'collection_date', 'collection_date_basis', 'original_source_version', 'internal_snapshot_version', 'provenance_status', 'layer', 'is_canon']
json.dump({'generated': meta['generated'], 'source': 'provenance_v1 (v9_01_quality_gate.py · ADR-0053) — 값을 지어내지 않는다: 없으면 unknown',
           'cols': cols, 'rows': [list(r) for r in prov]},
          open(os.path.join(SITE, 'data_v4', 'provenance_v4.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(f"provenance_v4: {len(prov)} datasets")
con.close()
