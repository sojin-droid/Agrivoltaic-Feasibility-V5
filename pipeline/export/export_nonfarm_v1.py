# -*- coding: utf-8 -*-
"""비농지 제외(자동 + 위성사진 육안 검토) 결과 export — data_v4/nonfarm_v1.json (검토 고정본 통계 · 값 반영은 정본 ADR-0060).

대상: R2_promo 1MW 이상 후보 공간 5,645곳 (freeze_v1.py 산출 — pipeline/nonfarm_v1.py).
  nonfarm_v1.json      전국·규모 구간·제외 사유·시도별 감소, 판정 분포, 미검토 범위, 스탬프 (검토 결과 페이지가 읽는다)
사유별 MW 는 후보마다 그 후보에서 뺀 MW 를 사유별 제외 면적 비율로 나눈 값의 합이다(면적 → MW 환산 0.045 kW/㎡ 는 장부 면적 기준).
사용: python pipeline/export/export_nonfarm_v1.py
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, NF
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
import pandas as pd
import nonfarm_v1 as NF1

T = NF1.table().reset_index()
KB = json.load(open(os.path.join(os.path.dirname(NF), '..', 'nonfarm_keep_v1', 'build.json'), encoding='utf-8'))
PD = json.load(open(os.path.join(NF, 'esri_dates_summary.json'), encoding='utf-8'))
L = pd.read_parquet(os.path.join(NF, 'nonfarm_ledger.parquet'))
ST = json.load(open(os.path.join(NF, 'nonfarm_review_v1.json'), encoding='utf-8'))
T['cut_auto'] = T.mw0 - T.mw_auto
T['cut_eye'] = T.mw_auto - T.mw_final            # 사용자가 자동 제외를 되살린 후보는 음수일 수 있다

BANDS = [('50+', '50MW 이상'), ('20-50', '20–50MW'), ('10-20', '10–20MW'), ('3-10', '3–10MW'), ('1-3', '1–3MW')]
r1 = lambda v: round(float(v), 1)


def tot(d):
    return {'n': int(len(d)), 'n_reviewed': int(d.reviewed.sum()), 'mw0': r1(d.mw0.sum()), 'mw_auto': r1(d.mw_auto.sum()),
            'mw_final': r1(d.mw_final.sum()), 'km2_0': round(d.a0.sum() / 1e6, 2), 'km2_final': round(d.a_final.sum() / 1e6, 2)}


bands = [{'band': b, 'label': lb, **tot(T[T.band == b])} for b, lb in BANDS]

# 사유별 — 눈 검토
eye = [c for c in T.columns if c.startswith('cut_') and c not in ('cut_road', 'cut_building', 'cut_strip', 'cut_auto', 'cut_eye')]
A = T[eye].fillna(0).clip(lower=0); s = A.sum(axis=1).replace(0, np.nan)
mw_eye = A.div(s, axis=0).mul(T.cut_eye.clip(lower=0), axis=0).sum()
le = L[L.stage == '눈 검토'].groupby('reason').agg(n=('pnu', 'size'), m2=('cut_m2', 'sum'))
# '사용자 판정' = 검토 회차에서 사용자가 사진을 보고 직접 뺀 필지(범주를 따로 적지 않음) — 발행 표에서는 '기타'로 합친다
MERGE = {'사용자 판정': '기타'}
ce = {}
for k in le.index:
    g = ce.setdefault(MERGE.get(k, k), {'parcels': 0, 'm2': 0.0, 'mw': 0.0})
    g['parcels'] += int(le.at[k, 'n']); g['m2'] += float(le.at[k, 'm2']); g['mw'] += float(mw_eye.get('cut_' + k, 0))
cat_eye = sorted([{'reason': k, 'parcels': v['parcels'], 'km2': round(v['m2'] / 1e6, 2), 'mw': r1(v['mw'])} for k, v in ce.items()],
                 key=lambda x: -x['mw'])
# 사유별 — 자동
AU = T[['cut_road', 'cut_building', 'cut_strip']].fillna(0); sa = AU.sum(axis=1).replace(0, np.nan)
mw_au = AU.div(sa, axis=0).mul(T.cut_auto, axis=0).sum()
la = L[L.stage == '자동'].groupby('reason').agg(n=('pnu', 'size'), m2=('cut_m2', 'sum'))
amap = {'도로(자동)': 'cut_road', '건물(자동)': 'cut_building', '폭 10m 미만 띠·200㎡ 미만 조각(자동)': 'cut_strip'}
cat_auto = [{'reason': k.replace('(자동)', ''), 'parcels': int(la.at[k, 'n']), 'km2': round(la.at[k, 'm2'] / 1e6, 2), 'mw': r1(mw_au[v])}
            for k, v in amap.items() if k in la.index]

SIDO = {'11': '서울', '26': '부산', '27': '대구', '28': '인천', '29': '광주', '30': '대전', '31': '울산', '36': '세종', '41': '경기',
        '42': '강원', '51': '강원', '43': '충북', '44': '충남', '45': '전북', '52': '전북', '46': '전남', '47': '경북', '48': '경남', '50': '제주'}
T['sido'] = T.sgg.astype(str).str[:2].map(SIDO)
sido = sorted([{'sido': k, **tot(d)} for k, d in T.groupby('sido')], key=lambda x: -x['mw0'])

R = T[T.reviewed]
out = {
    'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    'run': NF1.RUN, 'review_built_at': ST['built_at'], 'user_rounds': ST['user_rounds'],
    'kw_per_m2': 0.045, 'min_m2': 22222,
    'total': tot(T),
    'reviewed': {**tot(R), 'verdict': {k: int(v) for k, v in R.verdict.value_counts().items()},
                 'n_below_1mw': int((R.mw_final < 1).sum()), 'n_gone': int((R.a_final <= 0).sum())},
    'unreviewed': {**tot(T[~T.reviewed])},
    'n_gone_all': int((T.a_final <= 0).sum()), 'n_ge1_after': int((T.a_final >= 22222).sum()),
    'n_ge50_before': int((T.a0 >= 1111111).sum()), 'n_ge50_after': int((T.a_final >= 1111111).sum()),
    'bands': bands, 'reasons_eye': cat_eye, 'reasons_auto': cat_auto, 'sido': sido,
    'parcels_removed': {'auto': int((L.stage == '자동').sum()), 'eye': int((L.stage == '눈 검토').sum()), 'unique': int(L.pnu.nunique())},
    # 정본 반영(ADR-0060) — 필지 단위 남은 비율 표 nonfarm_keep_v1 의 집계(model/stages/v11_01_nonfarm_keep.py build.json)
    'keep': {k: KB[k] for k in ('n_parcel', 'n_drop', 'n_partial', 'a_ledger_km2', 'a_keep_km2', 'built_at')},
    # 위성사진 촬영 시점 — Esri 는 후보마다 가장 최근 촬영 연도의 분포, V-World 는 촬영일 미제공
    'photo_dates': {k: PD[k] for k in ('n_reviewed', 'year_min', 'year_max', 'share_ge2023_pct', 'share_ge2025_pct', 'vworld')},
    # 자동 제외에 쓴 자료의 판·시점(근거와 방법 페이지가 그대로 적는다)
    'sources': {'nodelink': '국토교통부 표준노드링크 2026-07-16판', 'osm': 'OpenStreetMap — Geofabrik 대한민국 추출본(2026-10-06 기준)',
                'building': 'V-World GIS건물통합정보(LT_C_BLDGINFO) — 2026-10-08 전국 수집'},
}
json.dump(out, open(os.path.join(SITE, 'data_v4', 'nonfarm_v1.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, allow_nan=False)

t = out['total']
print(f"nonfarm_v1: {t['n']:,}곳 · {t['mw0']:,} → 자동 {t['mw_auto']:,} → 최종 {t['mw_final']:,} MW · 육안 검토 {t['n_reviewed']:,}곳 · 검토 후 1MW 이상 {out['n_ge1_after']:,}곳")
