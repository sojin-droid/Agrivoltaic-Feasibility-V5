# -*- coding: utf-8 -*-
"""method_comparison_sites.csv 에 1MW 등가(≥22,222㎡) 클러스터 수를 추가한다 — 저장된 실행 결과(assignment·clusters)에서 다시 센다(재실행 없음).
집계 집합은 원래 지표와 같은 touch(해당 시군 필지를 하나라도 가진 클러스터)."""
import os, sys, json, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd
LR = r'C:\Users\user\새 폴더\Ledger_Rebuild'; SITE = r'C:\Users\user\Agrivoltaic-V5'
ROOT = os.path.join(LR, 'experiments', 'cluster_method_sites_20261007')
csv = os.path.join(SITE, 'docs', 'method_advisory', 'data', 'method_comparison_sites.csv')
df = pd.read_csv(csv, encoding='utf-8-sig')
idx = {}
for pj in glob.glob(os.path.join(ROOT, '*', '*', 'params.json')):
    P = json.load(open(pj, encoding='utf-8')); idx[P['params_hash']] = os.path.dirname(pj)
n1, s1 = [], []
for _, r in df.iterrows():
    d = idx[r.params_hash]; a = pd.read_parquet(os.path.join(d, 'assignment.parquet'), columns=['pnu', 'cluster_id']); g = pd.read_parquet(os.path.join(d, 'clusters.parquet'), columns=['cluster_id', 'area_m2'])
    ids = set(a.loc[a.pnu.str[:5] == str(r.sgg), 'cluster_id']); gs = g[g.cluster_id.isin(ids)]
    n1.append(int((gs.area_m2 >= 22_222).sum())); s1.append(round(float(gs.loc[gs.area_m2 < 22_222, 'area_m2'].sum() / gs.area_m2.sum()), 4))
df['n_ge1MW'] = n1; df['share_lt1MW'] = s1
cols = list(df.columns); cols.remove('n_ge1MW'); cols.remove('share_lt1MW')
i = cols.index('n_ge3MW'); cols = cols[:i] + ['n_ge1MW'] + cols[i:]; j = cols.index('share_lt3MW'); cols = cols[:j] + ['share_lt1MW'] + cols[j:]
df = df[cols]; df.to_csv(csv, index=False, encoding='utf-8-sig')
print(df.groupby('method')[['n_ge1MW', 'n_ge3MW', 'n_ge10MW', 'n_ge50MW']].median().to_string())
