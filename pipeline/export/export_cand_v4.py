# -*- coding: utf-8 -*-
"""후보 클러스터 층 export (ADR-0046 §6) — 엔진 산출(cand/ 또는 cand_subset/)을 사이트 data_v4 로 내보낸다. 발행에서 수치를 새로 만들지 않는다.

산출:
  data_v4/cand/{sgg}_{cell}.json.gz   시군 touch 구획 기준 cc 기하(4326, 단순화) + 속성 {id, am2, nc, n, iso, tb, td, hf, lo, d, labs}
  data_v4/recommend_cc_v4.json.gz     cells[cell].sgg[sgg] = {label, n_cc, n_multi, n_iso, bands{fm: n}, by_filter{fm: {n_pop, n_front, pop[…], frontier[…]}}}
                                      pop 행 = 모집단 전량(cand_frontier 그대로: 순위·front 플래그·좌표·front_labs)
  data_v4/cand_index.json             칸 × 시군 요약 + 스탬프(subset 여부 포함)
두 화면(regions·local)은 이 두 파일만 소비한다. 화면은 계산하지 않는다.
사용: python pipeline/export/export_cand_v4.py [--cells R2_promo ...] [--subset] [--site DIR]
"""
import os, sys, json, gzip, argparse, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np, pandas as pd, geopandas as gpd, shapely
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(HERE))
MODEL = os.environ.get('AGV_HOME', r'C:\Users\user\새 폴더\model')
sys.path.insert(0, MODEL)
from toolconf import RUNS
CELLS = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB', 'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
FILTERS = [66667, 222222, 444444, 1111111]
nz = lambda v, f=lambda x: x: None if v is None or (isinstance(v, float) and np.isnan(v)) else f(v)


def simplify_tol(am2):               # 크기 비례 단순화(runs_v4.SIMPLIFY 정신) — 원본은 엔진 gpkg 에 있다
    return 3.0 if am2 < 66667 else 5.0 if am2 < 1111111 else 8.0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--cells', nargs='+', default=CELLS); ap.add_argument('--subset', action='store_true'); ap.add_argument('--site', default=SITE)
    a = ap.parse_args()
    out_dir = os.path.join(a.site, 'data_v4', 'cand'); os.makedirs(out_dir, exist_ok=True)
    rec4 = json.load(gzip.open(os.path.join(a.site, 'data_v4', 'recommend_v4.json.gz'), 'rt', encoding='utf-8'))
    sm = json.load(open(os.path.join(a.site, 'data_v4', 'sgg_matrix.json'), encoding='utf-8'))['codes']
    name_of = lambda s: (sm.get(s) or {}).get('name', s)
    rec = {'rule': 'cond-inv', 'built': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'status': '', 'filters_m2': FILTERS, 'cells': {},
           'note': 'ADR-0046. 후보 클러스터 = 연접 구획의 응축 단일연결·면적 가중 EOM(고정 T·최소 MW 없음). 최소 표시 규모는 모집단 필터 — 필터별 모집단·전선 사전 산출. MW 참고 환산 0.045 kW/㎡. 산단 거리 = cc 경계 최근접(구획 층 대표점 정의와 다름).'}
    index = {'generated': rec['built'], 'cells': {}, 'sgg': {}}
    subset_all = None
    for cell in a.cells:
        d = os.path.join(RUNS, cell, 'cand_subset' if a.subset else 'cand')
        need = ['cand_clusters.parquet', 'cand_members.parquet', 'cand_geom.gpkg', 'cand_context.parquet', 'cand_frontier.parquet', 'cand_clusters.json']
        if not all(os.path.exists(os.path.join(d, f)) for f in need):
            print(f'  skip {cell}: 산출 미완'); continue
        st = json.load(open(os.path.join(d, 'cand_clusters.json'), encoding='utf-8'))
        subset_all = st.get('subset')
        cand = pd.read_parquet(os.path.join(d, 'cand_clusters.parquet')).set_index('cc_id')
        cm = pd.read_parquet(os.path.join(d, 'cand_members.parquet'))
        labs_of = cm.groupby('cc_id')['lab'].agg(list)
        ctx = pd.read_parquet(os.path.join(d, 'cand_context.parquet'))
        fr = pd.read_parquet(os.path.join(d, 'cand_frontier.parquet'))
        geo = gpd.read_file(os.path.join(d, 'cand_geom.gpkg')).set_index('cc_id').to_crs(4326)
        rec['cells'][cell] = {'sgg': {}}; index['cells'][cell] = {'n_cc': int(len(cand)), 'stamp': {k: st[k] for k in ('rule', 'tau_max_m', 'subset', 'built_at', 'n_cc', 'n_isolated')}}
        sggs = sorted(set(ctx['sgg'])) if not subset_all else [s for s in subset_all]
        for s in sggs:
            cx = ctx[ctx['sgg'] == s]
            ids = cx['cc_id'].tolist()
            front_labs = {f['lab'] for f in rec4['sgg'].get(s, {}).get('frontier', [])} if cell == 'R2_promo' else set()
            feats = []
            for cid in ids:
                r = cand.loc[cid]; c = cx[cx['cc_id'] == cid].iloc[0]
                g = geo.geometry.get(cid)
                if g is None: continue
                g = shapely.simplify(g, simplify_tol(r['area_m2']) / 111000.0)
                try:                                                                   # 좌표 5자리(≈1m) — 파일 크기. 위상 충돌 시 유효화 후 재시도, 그래도 실패면 반올림 생략
                    g = shapely.set_precision(g, 1e-5)
                except Exception:
                    try: g = shapely.set_precision(shapely.make_valid(g), 1e-5)
                    except Exception: pass
                feats.append({'type': 'Feature', 'geometry': json.loads(shapely.to_geojson(g)),
                              'properties': {'id': int(cid), 'am2': round(float(r['area_m2'])), 'nc': int(r['n_component']), 'n': int(r['n_parcel']), 'iso': bool(r['is_isolated']),
                                             'tb': nz(r['t_birth_m'], round), 'td': nz(r['t_death_m'], round), 'hf': nz(r['hull_fill'], lambda x: round(x, 2)),
                                             'lo': nz(c['lo'], lambda x: round(x, 1)), 'd': nz(c['dist_ind_km'], lambda x: round(x, 2)), 'labs': [int(x) for x in labs_of.get(cid, [])]}})
            with gzip.open(os.path.join(out_dir, f'{s}_{cell}.json.gz'), 'wt', encoding='utf-8') as f:
                json.dump({'type': 'FeatureCollection', 'cell': cell, 'sgg': s, 'rule': 'cond-inv', 'features': feats}, f, ensure_ascii=False, separators=(',', ':'))
            by = {}
            for fm in FILTERS:
                g = fr[(fr['sgg'] == s) & (fr['min_area_m2'] == fm)].sort_values('area_m2', ascending=False)
                pop = []
                for r in g.itertuples():
                    L = [int(x) for x in labs_of.get(r.cc_id, [])]
                    pop.append({'id': int(r.cc_id), 'a': round(float(r.area_m2)), 'mw': round(float(r.mw_ref), 1), 'lo': nz(r.lo, lambda x: round(x, 1)), 'd': nz(r.dist_ind_km, lambda x: round(x, 2)),
                                'ra': int(r.r_area), 'rl': int(r.r_lo), 'ri': int(r.r_ind), 'front': bool(r.front), 'strong': r.strong or '',
                                'nc': int(r.n_component), 'n': int(r.n_parcel), 'iso': bool(r.is_isolated), 'tb': nz(r.t_birth_m, round), 'td': nz(r.t_death_m, round),
                                'lat': nz(r.y, lambda v: round(v, 5)), 'lon': nz(r.x, lambda v: round(v, 5)), 'recl': nz(r.reclaim_pct, lambda v: round(v, 1)),
                                'labs': L, 'front_labs': [l for l in L if l in front_labs]})
                by[str(fm)] = {'n_pop': int(len(pop)), 'n_front': int(sum(1 for x in pop if x['front'])), 'pop': pop, 'frontier': [x for x in pop if x['front']]}
            n_cc = int(len(ids)); n_multi = int((cand.loc[ids, 'n_component'] > 1).sum()); n_iso = int(cand.loc[ids, 'is_isolated'].sum())
            rec['cells'][cell]['sgg'][s] = {'label': name_of(s), 'n_cc': n_cc, 'n_multi': n_multi, 'n_iso': n_iso,
                                            'bands': {str(fm): int((cand.loc[ids, 'area_m2'] >= fm).sum()) for fm in [0] + FILTERS}, 'by_filter': by}
            index['sgg'].setdefault(s, {})[cell] = {'n_cc': n_cc, 'n_multi': n_multi, 'n_iso': n_iso, 'km2': round(float(cand.loc[ids, 'area_m2'].sum()) / 1e6, 3), 'n_front_3mw': by['66667']['n_front']}
            print(f'  {s} {cell}: cc {n_cc:,} · 3MW 모집단 {by["66667"]["n_pop"]} 전선 {by["66667"]["n_front"]}')
    rec['status'] = f"{'subset ' + ','.join(subset_all) if subset_all else '전국'} · ADR-0046 · 엔진 산출 export"
    index['status'] = rec['status']
    with gzip.open(os.path.join(a.site, 'data_v4', 'recommend_cc_v4.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, separators=(',', ':'))
    json.dump(index, open(os.path.join(a.site, 'data_v4', 'cand_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('written recommend_cc_v4.json.gz · cand_index.json · cand/*')


if __name__ == '__main__':
    main()
