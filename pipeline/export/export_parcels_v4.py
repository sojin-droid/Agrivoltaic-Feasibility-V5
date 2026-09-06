# -*- coding: utf-8 -*-
"""적격 필지 검증 레이어 export (ADR-0045 ②) — 시군별 점 파일.

목적: 데이터 검증자가 지도에서 "적격 필지 전량(연한 점) 위에 연접 구획(진한
폴리곤)이 정확히 얹히고, 소유가 법인·국공유가 맞다"를 눈으로 확인.
원천: R2_promo(정본 우주) members 전량 = 적격 필지 전량(모든 적격 필지는 어느
구획엔가 속함) + engine_cache/parcel_points(대표점, EPSG:5186) + ledger.ownership.
출력: data_v4/parcels/{sgg}.json.gz — {"own_legend":…, "pts":[[lon,lat,ownIdx],…]}
게이트: 시군별 점 수 = members 필지 수 정확 일치(좌표 결손은 건수 보고).
"""
import os, sys, json, gzip
import duckdb
import numpy as np
from pyproj import Transformer

LR = r"C:\Users\user\새 폴더\Ledger_Rebuild"
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(SITE, 'data_v4', 'parcels')
os.makedirs(OUT, exist_ok=True)
P = lambda p: p.replace('\\', '/')

con = duckdb.connect(os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb'), read_only=True)
mem_p = P(os.path.join(LR, 'scenario_runs', 'R2_promo', 'members.parquet'))
pp_p = P(os.path.join(LR, 'engine_cache', 'parcel_points.parquet'))

df = con.execute(f"""
  SELECT m.pnu, m.lab, substr(m.pnu,1,5) AS sgg, p.x, p.y, l.ownership
  FROM read_parquet('{mem_p}') m
  LEFT JOIN read_parquet('{pp_p}') p USING(pnu)
  LEFT JOIN ledger l USING(pnu)""").fetch_df()
n_all = len(df)
n_noxy = int(df['x'].isna().sum())
print(f"적격 필지 {n_all:,} · 좌표 결손 {n_noxy:,} ({100*n_noxy/n_all:.2f}%)")

OWNS = ['02', '04', '05', '06']          # 국유·시도유·군유·법인 (정본 우주)
own_idx = {c: i for i, c in enumerate(OWNS)}
bad_own = ~df['ownership'].isin(OWNS)
assert bad_own.sum() == 0, f"정본 우주 밖 소유 코드 발견: {df.loc[bad_own,'ownership'].unique()}"

ok = df[df['x'].notna()].copy()
tr = Transformer.from_crs(5186, 4326, always_xy=True)
lon, lat = tr.transform(ok['x'].to_numpy(), ok['y'].to_numpy())
ok['lon'] = np.round(lon, 5)
ok['lat'] = np.round(lat, 5)
ok['oi'] = ok['ownership'].map(own_idx)

legend = {i: {'02': '국유지', '04': '시/도유지', '05': '군유지', '06': '법인'}[c]
          for c, i in own_idx.items()}
sizes = []
for sgg, g in ok.groupby('sgg'):
    pts = g[['lon', 'lat', 'oi']].to_numpy()
    obj = {'sgg': sgg, 'n': int(len(g)),
           'n_total': int((df['sgg'] == sgg).sum()),   # 좌표 결손 포함 전량 — 대조용
           'own_legend': legend,
           'pts': [[float(a), float(b), int(c)] for a, b, c in pts]}
    fp = os.path.join(OUT, f'{sgg}.json.gz')
    with gzip.open(fp, 'wt', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    sizes.append(os.path.getsize(fp))

idx = {'generated': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'),
       'run': 'R2_promo', 'n_parcel': n_all, 'n_no_xy': n_noxy,
       'sgg': sorted(ok['sgg'].unique().tolist()), 'own_legend': legend,
       'note': '적격 필지 전량(정본 우주·R2) 대표점 — 검증 표시 전용, 판정 불사용. '
               '좌표 결손 필지는 점 없이 건수로만 보고(n_total-n).'}
json.dump(idx, open(os.path.join(OUT, '_index.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(f"저장 {len(sizes)}개 시군 · 합 {sum(sizes)/1e6:.1f} MB · 최대 {max(sizes)/1e3:.0f} KB")
