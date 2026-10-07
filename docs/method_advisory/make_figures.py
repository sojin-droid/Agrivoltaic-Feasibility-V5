# -*- coding: utf-8 -*-
"""방법론 자문 브리프용 원자료 분포 그림 (자문용 기술 통계 — 정본 수치가 아니다).

입력은 정본 산출만 읽는다(수정 없음):
  LR/step4_1_gaps_S1.parquet · LR/step4_1_kneedle_S1.csv          (21m 유도 — k-거리)
  LR/scenario_runs/R2_promo/clusters.parquet                       (21m 연접 단위 전량 388,121 — 면적 하한 없음)
  LR/scenario_runs/R2_promo/block_context.parquet                  (3축 입력 — 2026-10-07 부터 전량 388,496행 · 면적 하한 없음)
  DuckDB grid_emd_v3                                               (읍면동 계통 참고값)
  SITE/data_v4/ind_bnd.json.gz                                     (산업단지 경계 1,363)
  SITE/data_v4/top10/*.json.gz                                     (시군×칸 비지배 플래그 — 발행 자산)
출력: docs/method_advisory/fig/*.png · docs/method_advisory/data/*.csv (그림의 수치 그대로)
"""
import os, sys, json, gzip, glob, csv
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import duckdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

LR = r'C:\Users\user\새 폴더\Ledger_Rebuild'
SITE = r'C:\Users\user\Agrivoltaic-V5'
RUN = os.path.join(LR, 'scenario_runs', 'R2_promo')
OUT = os.path.join(SITE, 'docs', 'method_advisory')
FIG, DATA = os.path.join(OUT, 'fig'), os.path.join(OUT, 'data')
os.makedirs(FIG, exist_ok=True); os.makedirs(DATA, exist_ok=True)

plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False, 'font.size': 9,
                     'axes.labelsize': 9.5, 'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5, 'legend.fontsize': 8.5,
                     'axes.linewidth': 0.8, 'lines.linewidth': 1.4})
NAVY, RED, GOLD, GRAY, TEAL, LEAF = '#1c2b4a', '#B3261E', '#B8860B', '#9aa3ae', '#1D6F8A', '#2E7D4F'
KW = 0.045
MW = {'3MW': 66_667, '10MW': 222_222, '20MW': 444_444, '50MW': 1_111_111}
LOG = []

def save(fig, name):
    fig.savefig(os.path.join(FIG, name + '.png'), bbox_inches='tight', dpi=170)
    plt.close(fig); print('  fig', name)

def q(a, ps=(5, 25, 50, 75, 95)):
    return {f'p{p}': float(np.percentile(a, p)) for p in ps}

def write_csv(name, rows, header):
    with open(os.path.join(DATA, name + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print('  csv', name)

# ── 1. k-거리 곡선 (k = 1·2·4·8·12) + 무릎 표 ─────────────────────────────
print('1 k-distance')
g = pq.read_table(os.path.join(LR, 'step4_1_gaps_S1.parquet'), columns=['d1', 'd2', 'd4', 'd8', 'd12']).to_pandas()
knee = pd.read_csv(os.path.join(LR, 'step4_1_kneedle_S1.csv'), encoding='utf-8-sig')
fig, ax = plt.subplots(figsize=(6.2, 3.6))
cols = {'d1': GRAY, 'd2': TEAL, 'd4': NAVY, 'd8': LEAF, 'd12': GOLD}
rows = []
for k, c in cols.items():
    d = np.sort(g[k].dropna().to_numpy())[::-1]; n = len(d); pct = np.arange(1, n + 1) / n * 100
    step = max(1, n // 20000)
    ax.plot(pct[::step], d[::step], color=c, lw=1.6 if k == 'd4' else 1.0, label=f'k = {k[1:]} (n = {n:,})')
    kk = knee[(knee.k == int(k[1:])) & (knee.S == 2)].iloc[0]
    rows.append([int(k[1:]), n, round(float(kk.knee_m), 2), round(float(kk.knee_pct), 2)] + [round(v, 2) for v in q(d).values()])
ax.axhline(21, color=RED, lw=1.1); ax.text(99, 23.5, 'τ = 21 m', ha='right', color=RED, fontsize=8.5)
ax.axhspan(20.0, 21.6, color=RED, alpha=.12, lw=0)
ax.set_xlabel('필지 백분위 (%, k-최근접 경계 거리 내림차순)'); ax.set_ylabel('k-최근접 적격 필지까지 경계 거리 (m)')
ax.set_xlim(0, 100); ax.set_ylim(0, 120); ax.legend(frameon=False, ncol=3, loc='lower center', bbox_to_anchor=(0.5, 1.01))
save(fig, 'f01_kdistance_curves')
write_csv('f01_kdistance_knee', rows, ['k', 'n', 'knee_m_S2', 'knee_pct_S2', 'p5', 'p25', 'p50', 'p75', 'p95'])
write_csv('f01_kneedle_all', knee.values.tolist(), list(knee.columns))

# 1b. 4-최근접 간격 히스토그램 (0–200 m · 로그 y)
d4 = g['d4'].dropna().to_numpy()
fig, ax = plt.subplots(figsize=(6.2, 3.2))
ax.hist(np.clip(d4, 0, 200), bins=200, color=NAVY, alpha=.85); ax.set_yscale('log')
ax.axvline(21, color=RED, lw=1.1); ax.text(23, ax.get_ylim()[1] * .5, 'τ = 21 m', color=RED, fontsize=8.5)
for v, lab in ((15, '15'), (25, '25')): ax.axvline(v, color=GRAY, lw=.8, ls='--')
ax.set_xlabel('4-최근접 적격 필지까지 경계 거리 (m) — 200 m 초과는 200에 모음'); ax.set_ylabel('필지 수 (로그)')
save(fig, 'f02_gap_hist_d4')
share = [[t, int((d4 <= t).sum()), round(float((d4 <= t).mean() * 100), 2)] for t in (0, 5, 10, 15, 21, 25, 30, 50, 100, 200, 500, 1000)]
write_csv('f02_gap_share_d4', share, ['threshold_m', 'n_le', 'pct_le'])
LOG.append(('d4 n', len(d4)))

# ── 2. 21m 연접 단위 면적·필지 수 분포 (전량 388,121 · 하한 없음) ─────────────
print('2 unit area')
cl = pq.read_table(os.path.join(RUN, 'clusters.parquet'), columns=['lab', 'n_parcel', 'area_m2']).to_pandas()
a = cl.area_m2.to_numpy(); a_pos = a[a > 0]
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.4))
ax = axs[0]
bins = np.logspace(1, 7.2, 70)
ax.hist(a_pos, bins=bins, color=NAVY, alpha=.85); ax.set_xscale('log'); ax.set_yscale('log')
for k, v in MW.items():
    ax.axvline(v, color=RED if k in ('3MW', '50MW') else GRAY, lw=.9, ls='--'); ax.text(v * 1.08, ax.get_ylim()[1] * .55, k, fontsize=8, color=RED if k in ('3MW', '50MW') else GRAY, rotation=90, va='top')
ax.set_xlabel('후보 공간 면적 (㎡, 로그) — 0.045 kW/㎡ 환산 눈금 표시'); ax.set_ylabel('후보 공간 수 (로그)')
ax = axs[1]
npc = cl.n_parcel.to_numpy()
vals, cnts = np.unique(np.clip(npc, 1, 200), return_counts=True)
ax.bar(vals, cnts, width=1, color=TEAL); ax.set_yscale('log'); ax.set_xlabel('구성 필지 수 (200 초과는 200에 모음)'); ax.set_ylabel('후보 공간 수 (로그)')
save(fig, 'f03_unit_area_parcels')
sizerows = []
for k, v in [('전체', 0)] + list(MW.items()):
    m = a >= v
    sizerows.append([k, v, int(m.sum()), round(float(a[m].sum() / 1e6), 2), round(float(np.median(a[m])), 0) if m.any() else '', round(float(np.median(npc[m])), 1) if m.any() else ''])
write_csv('f03_unit_size_bands', sizerows, ['band', 'min_m2', 'n_units', 'area_km2', 'median_area_m2', 'median_n_parcel'])
write_csv('f03_unit_area_quantiles', [[k, round(v, 1)] for k, v in q(a, (1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9)).items()] + [['n_total', len(a)], ['n_single_parcel', int((npc == 1).sum())], ['n_area0', int((a == 0).sum())]], ['stat', 'value'])

# ── 3. 3축 입력 분포 — block_context (전량 · 면적 하한 없음) ─────
print('3 axes')
bc = pq.read_table(os.path.join(RUN, 'block_context.parquet')).to_pandas()
LOG.append(('block_context n', len(bc), 'min area', float(bc.area_m2.min())))
fig, axs = plt.subplots(1, 3, figsize=(11, 3.3))
ax = axs[0]; ax.hist(np.log10(bc.area_m2[bc.area_m2 > 0]), bins=60, color=NAVY, alpha=.85)
for k, v in MW.items(): ax.axvline(np.log10(v), color=GRAY, lw=.8, ls='--')
ax.set_xlabel('A 면적 log10(㎡)'); ax.set_ylabel('후보 공간 수')
ax = axs[1]; lo = bc.lo.to_numpy(); lo_ok = lo[~np.isnan(lo)]
ax.hist(np.clip(lo_ok, 0, 300), bins=60, color=TEAL, alpha=.85); ax.set_xlabel('B 계통 여유 참고값 하한 (MW · 읍면동 단위 · 300 초과는 300에 모음)'); ax.set_ylabel('후보 공간 수')
ax.text(.98, .95, f'결측(알 수 없음) {int(np.isnan(lo).sum()):,} / {len(lo):,}', transform=ax.transAxes, ha='right', va='top', fontsize=8, color=RED)
ax = axs[2]; d = bc.dist_ind_km.to_numpy(); d_ok = d[~np.isnan(d)]
ax.hist(np.clip(d_ok, 0, 40), bins=60, color=LEAF, alpha=.85); ax.set_xlabel('C 가장 가까운 산업단지 경계까지 거리 (km · 40 초과는 40에 모음)'); ax.set_ylabel('후보 공간 수')
ax.text(.98, .95, f'결측 {int(np.isnan(d).sum()):,}', transform=ax.transAxes, ha='right', va='top', fontsize=8, color=RED)
save(fig, 'f04_axes_hist')
write_csv('f04_axes_quantiles', [['A_area_m2'] + [round(v, 0) for v in q(bc.area_m2.to_numpy()).values()], ['B_lo_mw'] + [round(v, 1) for v in q(lo_ok).values()], ['C_dist_ind_km'] + [round(v, 2) for v in q(d_ok).values()]], ['axis', 'p5', 'p25', 'p50', 'p75', 'p95'])

# 3b. 축 간 산점도·순위상관 (3MW 이상 = TOP 10 모집단)
m3 = bc[bc.area_m2 >= MW['3MW']].copy()
fig, axs = plt.subplots(1, 3, figsize=(11, 3.4))
pairs = [('area_m2', 'lo', 'A 면적 (㎡, 로그)', 'B 계통 하한 (MW)'), ('area_m2', 'dist_ind_km', 'A 면적 (㎡, 로그)', 'C 산단 거리 (km)'), ('lo', 'dist_ind_km', 'B 계통 하한 (MW)', 'C 산단 거리 (km)')]
corr_rows = []
for ax, (x, y, xl, yl) in zip(axs, pairs):
    s = m3[[x, y]].dropna()
    ax.scatter(s[x], s[y], s=6, alpha=.35, color=NAVY, lw=0)
    if x == 'area_m2': ax.set_xscale('log')
    rho, p = spearmanr(s[x], s[y]); ax.set_xlabel(xl); ax.set_ylabel(yl)
    ax.text(.02, .95, f'Spearman ρ = {rho:.2f} (n = {len(s):,})', transform=ax.transAxes, va='top', fontsize=8)
    corr_rows.append([x, y, len(s), round(float(rho), 3), float(p)])
save(fig, 'f05_axes_scatter_3mw')
write_csv('f05_axes_spearman_3mw', corr_rows, ['x', 'y', 'n', 'spearman_rho', 'p'])

# ── 4. 반경 안 산업단지 개수 (자문용 탐색 — 정본 축 아님) ──────────────────────
print('4 ind count')
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from pyproj import Transformer
ind = json.load(gzip.open(os.path.join(SITE, 'data_v4', 'ind_bnd.json.gz'), 'rt', encoding='utf-8'))
tr = Transformer.from_crs('EPSG:4326', 'EPSG:5186', always_xy=True)
from shapely.ops import transform as sh_transform
polys, types = [], []
for f in ind['features']:
    try:
        gm = sh_transform(tr.transform, shape(f['geometry']))
        if not gm.is_empty: polys.append(gm); types.append(f['properties'].get('t', ''))
    except Exception: pass
tree = STRtree(polys)
pts = [Point(x, y) for x, y in zip(m3.x, m3.y)]
# 좌표계 점검: 정본 최근접 거리(dist_ind_km)와 재계산 최근접 거리 비교
near = tree.nearest(pts)
recomp = np.array([pts[i].distance(polys[int(j)]) / 1000 for i, j in enumerate(near)])
chk = np.nanmedian(np.abs(recomp - m3.dist_ind_km.to_numpy()))
LOG.append(('ind nearest recompute median abs diff km', round(float(chk), 3)))
radii = (5, 10, 20)
cnt = {r: np.zeros(len(pts), int) for r in radii}
for i, p in enumerate(pts):
    for r in radii:
        idx = tree.query(p.buffer(r * 1000))
        cnt[r][i] = sum(1 for j in idx if polys[int(j)].distance(p) <= r * 1000)
fig, axs = plt.subplots(1, 3, figsize=(11, 3.2))
fig.suptitle('산업단지 경계까지 거리 기준 · 30 초과는 30에 모음', fontsize=8.5, color='#555', y=1.02)
for ax, r in zip(axs, radii):
    v = cnt[r]; vals, c = np.unique(np.clip(v, 0, 30), return_counts=True)
    ax.bar(vals, c, color=GOLD); ax.set_xlabel(f'반경 {r} km 안 산업단지 수'); ax.set_ylabel('후보 공간 수')
    ax.text(.98, .95, f'0곳 {int((v == 0).sum()):,} / {len(v):,}', transform=ax.transAxes, ha='right', va='top', fontsize=8)
save(fig, 'f06_ind_count_radius')
write_csv('f06_ind_count_quantiles', [[r] + [int(x) for x in np.percentile(cnt[r], (5, 25, 50, 75, 95))] + [int((cnt[r] == 0).sum())] for r in radii], ['radius_km', 'p5', 'p25', 'p50', 'p75', 'p95', 'n_zero'])
write_csv('f06_ind_types', [[t, c] for t, c in pd.Series(types).value_counts().items()], ['type', 'n'])

# ── 5. 읍면동 계통 참고값 분포 (grid_emd_v3) ──────────────────────────────
print('5 grid emd')
con = duckdb.connect(os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb'), read_only=True)
ge = con.execute("select emd8, status, n_dl, vol3_equal_mw, vol3_shared_mw from grid_emd_v3").df()
con.close()
st = ge.status.value_counts()
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.2))
ax = axs[0]; ok = ge.vol3_equal_mw.dropna().to_numpy()
ax.hist(np.clip(ok, 0, 300), bins=60, color=TEAL, alpha=.85); ax.set_xlabel('읍면동 계통 여유 참고값 (MW · 균등 배분 · 300 초과는 300)'); ax.set_ylabel('읍면동 수')
ax = axs[1]; ax.bar(range(len(st)), st.values, color=[NAVY, GRAY, RED, GOLD][:len(st)]); ax.set_xticks(range(len(st))); ax.set_xticklabels(st.index, fontsize=8); ax.set_ylabel('읍면동 수'); ax.set_xlabel('조회 상태')
save(fig, 'f07_grid_emd')
write_csv('f07_grid_emd_status', [[k, int(v)] for k, v in st.items()] + [['vol3_equal_' + k, round(v, 1)] for k, v in q(ok).items()] + [['n_dl_median', float(ge.n_dl.median())]], ['stat', 'value'])

# ── 6. 시군별 모집단 크기와 비지배 비율 (data_v4/top10 · R2_promo · 3MW 이상) ────
print('6 frontier share')
rows = []
for f in sorted(glob.glob(os.path.join(SITE, 'data_v4', 'top10', '*.json.gz'))):
    t = json.load(gzip.open(f, 'rt', encoding='utf-8')); c = t['runs'].get('R2_promo')
    if not c: continue
    cols = t['cols']; ia, i3, iab, iac, ibc = (cols.index(k) for k in ('a', 'f3', 'fab', 'fac', 'fbc'))
    r3 = [r for r in c['rows'] if r[ia] >= MW['3MW']]
    if not r3: continue
    rows.append([t['sgg'], t.get('label', ''), len(r3), sum(1 for r in r3 if r[i3]), sum(1 for r in r3 if r[iab]), sum(1 for r in r3 if r[iac]), sum(1 for r in r3 if r[ibc])])
fr = pd.DataFrame(rows, columns=['sgg', 'label', 'n_3mw', 'nd_3ax', 'nd_ab', 'nd_ac', 'nd_bc'])
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.4))
ax = axs[0]
for col, lab, c in (('nd_3ax', '3축 (A+B+C)', NAVY), ('nd_ab', 'A+B', TEAL), ('nd_ac', 'A+C', LEAF), ('nd_bc', 'B+C', GOLD)):
    ax.scatter(fr.n_3mw, fr[col] / fr.n_3mw, s=14, alpha=.7, color=c, lw=0, label=lab)
ax.set_xscale('log'); ax.set_xlabel('시군 모집단 (3MW 이상 후보 공간 수, 로그)'); ax.set_ylabel('비지배(주요 비교 후보) 비율'); ax.set_ylim(0, 1.02); ax.legend(frameon=False, fontsize=8)
ax = axs[1]
ax.hist(fr.nd_3ax, bins=range(0, int(fr.nd_3ax.max()) + 2), color=NAVY, alpha=.85); ax.set_xlabel('시군별 3축 비지배 후보 수'); ax.set_ylabel('시군 수')
save(fig, 'f08_frontier_share_by_population')
write_csv('f08_frontier_share_by_sgg', fr.values.tolist(), list(fr.columns))
bins = [(1, 1), (2, 4), (5, 9), (10, 19), (20, 49), (50, 10 ** 6)]
agg = []
for lo_, hi_ in bins:
    s = fr[(fr.n_3mw >= lo_) & (fr.n_3mw <= hi_)]
    if len(s): agg.append([f'{lo_}–{hi_ if hi_ < 10**6 else ""}', len(s), int(s.n_3mw.sum()), int(s.nd_3ax.sum()), round(float(s.nd_3ax.sum() / s.n_3mw.sum()), 3), round(float((s.nd_3ax / s.n_3mw).median()), 3)])
write_csv('f08_frontier_share_by_popbin', agg, ['pop_bin', 'n_sgg', 'sum_pop', 'sum_nd3', 'pooled_share', 'median_share'])

with open(os.path.join(DATA, 'README.md'), 'w', encoding='utf-8') as f:
    f.write('# 그림 데이터 (자문용 기술 통계)\n\n정본 산출을 읽어 만든 분포 요약이다. 정본 수치가 아니며 인용은 `model/query.py` 산출로 한다.\n\n')
    f.write('| 파일 | 내용 | 원천 |\n|---|---|---|\n')
    for n, d_, s in [('f01_*', 'k-거리 곡선 무릎·분위', 'step4_1_gaps_S1.parquet · step4_1_kneedle_S1.csv'), ('f02_*', '4-최근접 간격 누적 비율', 'step4_1_gaps_S1.parquet'),
                     ('f03_*', '21m 단위 면적·필지 수(전량, 하한 없음)', 'scenario_runs/R2_promo/clusters.parquet'), ('f04_*·f05_*', '3축 분위·순위상관(3MW 이상)', 'scenario_runs/R2_promo/block_context.parquet'),
                     ('f06_*', '반경 안 산업단지 수(탐색)', 'block_context x,y × data_v4/ind_bnd.json.gz'), ('f07_*', '읍면동 계통 참고값', 'DuckDB grid_emd_v3'), ('f08_*', '시군 모집단 대 비지배 비율', 'data_v4/top10/*.json.gz R2_promo')]:
        f.write(f'| {n} | {d_} | {s} |\n')
    f.write('\n점검 로그: ' + ' · '.join(str(x) for x in LOG) + '\n')
print('LOG', LOG)
print('done')
