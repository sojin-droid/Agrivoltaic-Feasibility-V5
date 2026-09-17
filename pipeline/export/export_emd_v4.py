# -*- coding: utf-8 -*-
"""읍면동 후보군 export (ADR-0048 · PR-0044 §15 · PR-0046 §4) — 엔진 산출 cand/emd_membership · emd_frontier 를 사이트 data_v4 로 내보낸다. 발행에서 수치를 새로 만들지 않는다.

산출:
  data_v4/recommend_emd_v4.json.gz   cells[cell].sgg[sgg] = {n_emd, n_emd_single_3mw, emd{emd8: {name, bnd, touch, grid{s,lo,hi}, by_filter{fm: {n_pop, n_front, single, rows[{id, sh, pr, fe, fs, ne}]}}}}
                                      · rows 의 id = recommend_cc_v4 pop 행의 cc id (속성은 화면이 그 파일에서 조인 — 중복 저장 없음)
                                      · sh = emd_share(표시용) · pr = primary · fe = 읍면동 비지배 · fs = 시군 비지배 · ne = 걸친 읍면동 수
                                      · 읍면동 키 = PNU 앞 8자리(법정동 구 코드 · 정본) · bnd = grid_emd.json 의 경계 코드(신 코드) — emd_alias 코드 다리, 없으면 null
  data_v4/emd_index.json             칸 × 시군 요약 + 코드 다리 매핑률 + 스탬프
읽기 규약(파일 note 에도 기록): frontier 수는 항상 n_pop 과 함께 · single(n_pop=1) 은 정의상 frontier(우수성 아님) · 걸침 cc 는 여러 읍면동에 등장하므로 읍면동별 수를 합산하지 않는다.
사용: python pipeline/export/export_emd_v4.py [--cells R2_promo ...] [--site DIR]
"""
import os, sys, json, gzip, argparse, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
SITE = os.path.dirname(os.path.dirname(HERE))
MODEL = os.environ.get('AGV_HOME', r'C:\Users\user\새 폴더\model'); sys.path.insert(0, MODEL)
from toolconf import RUNS, LR, DB
CELLS = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB', 'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
FILTERS = [66667, 222222, 444444, 1111111]
nz = lambda v, f=lambda x: x: None if v is None or (isinstance(v, float) and np.isnan(v)) else f(v)


def code_bridge(old_codes):
    """정본 emd8(구 코드) → grid_emd.json 경계 코드(신 코드). 경계에 같은 코드가 있으면 그대로, 없으면 emd_alias(이름 대조 + 공간 매칭)의 역방향."""
    import duckdb, geopandas as gpd
    from emd_alias import build_alias
    bnd = gpd.read_file(os.path.join(LR, 'sources', 'emd_bnd', 'emd_bnd.gpkg'))
    bnd_codes = set(str(x)[:8] for x in bnd['emd_cd'])
    con = duckdb.connect(DB, read_only=True)
    alias = build_alias(con, bnd, set(old_codes))          # {신: 구}
    con.close()
    rev = {}
    for new, old in alias.items(): rev.setdefault(old, new)
    bridge = {o: (o if o in bnd_codes else rev.get(o)) for o in old_codes}
    return bridge, {'n_old': len(old_codes), 'n_same_code': sum(1 for o in old_codes if o in bnd_codes), 'n_alias': sum(1 for o in old_codes if o not in bnd_codes and bridge[o]), 'n_unmapped': sum(1 for o in old_codes if bridge[o] is None)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--cells', nargs='+', default=CELLS); ap.add_argument('--site', default=SITE); a = ap.parse_args()
    out_p = os.path.join(a.site, 'data_v4', 'recommend_emd_v4.json.gz')
    rcc = json.load(gzip.open(os.path.join(a.site, 'data_v4', 'recommend_cc_v4.json.gz'), 'rt', encoding='utf-8'))
    grid = {f['properties']['c']: f['properties'] for f in json.load(gzip.open(os.path.join(a.site, 'data_v4', 'grid_emd.json.gz'), 'rt', encoding='utf-8'))['features']}
    rec = {'rule': 'ADR-0048 · PR-0046', 'built': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'filters_m2': FILTERS, 'cells': {},
           'note': '읍면동 후보군 = 그 읍면동에 필지를 가진 후보 클러스터(touch) 전량. 클러스터는 21m 연접 정의(ADR-0049) 그대로이며 읍면동으로 자르지 않는다. 읍면동 비지배(fe)는 그 읍면동 후보 사이에서 면적·계통 여유·산단 거리 3축에 지지 않는 후보(시군 비지배 fs 와 같은 함수). '
                   'frontier 수는 항상 후보 수(n_pop)와 함께 읽고, 후보가 1개인 읍면동(single)은 정의상 frontier 이므로 우수성으로 읽지 않는다. 걸침 클러스터(ne≥2)는 여러 읍면동에 나타나므로 읍면동별 수를 합산하지 않는다. 행의 속성은 recommend_cc_v4 의 같은 id 에서 읽는다.'}
    index = {'generated': rec['built'], 'cells': {}, 'code_bridge': None}
    bridge = None; stats = None
    for cell in a.cells:
        d = os.path.join(RUNS, cell, 'cand')
        if not all(os.path.exists(os.path.join(d, f)) for f in ['emd_membership.parquet', 'emd_frontier.parquet', 'emd_frontier.json']):
            print(f'  skip {cell}: emd_frontier 미산출'); continue
        if cell not in rcc['cells']:
            print(f'  skip {cell}: recommend_cc_v4 에 칸 없음'); continue
        st = json.load(open(os.path.join(d, 'emd_frontier.json'), encoding='utf-8'))
        if not st.get('self_check_sgg_as_one_emd', {}).get('PASS'): raise SystemExit(f'거부: {cell} emd_frontier 자기 대조 미통과')
        mem = pd.read_parquet(os.path.join(d, 'emd_membership.parquet')); ef = pd.read_parquet(os.path.join(d, 'emd_frontier.parquet'))
        if bridge is None:
            bridge, stats = code_bridge(sorted(set(mem['emd8'])))
            print(f"코드 다리: 읍면동 {stats['n_old']:,} · 동일 코드 {stats['n_same_code']:,} · alias {stats['n_alias']:,} · 미매핑 {stats['n_unmapped']:,}")
        else:
            extra = sorted(set(mem['emd8']) - set(bridge));
            if extra:
                b2, _ = code_bridge(extra); bridge.update(b2)
        # cc id 가 recommend_cc_v4 의 pop 에 실재하는지(속성 조인 가능) — 필터별 pop 은 그 필터 이상 cc 전량이므로 3MW 필터 pop 으로 검사
        pop_ids = {s: {int(p['id']) for p in v['by_filter'].get('66667', {}).get('pop', [])} for s, v in rcc['cells'][cell]['sgg'].items()}
        cell_out = {'sgg': {}}; n_missing_id = 0
        for s, g in ef.groupby('sgg'):
            emd_out = {}
            for e, ge in g.groupby('emd8'):
                by_f = {}
                for fm in FILTERS:
                    gf = ge[ge['min_area_m2'] == fm]
                    if len(gf) == 0: continue
                    rows = []
                    for r in gf.sort_values(['area_m2'], ascending=False).itertuples():
                        if int(r.cc_id) not in pop_ids.get(s, set()): n_missing_id += 1
                        rows.append({'id': int(r.cc_id), 'sh': round(float(r.emd_share), 3), 'pr': bool(r.is_primary_emd), 'fe': bool(r.in_emd_frontier), 'fs': bool(r.in_sgg_frontier), 'ne': int(r.n_emd_of_cluster)})
                    by_f[str(fm)] = {'n_pop': int(gf['n_pop'].iloc[0]), 'n_front': int(gf['n_front'].iloc[0]), 'single': bool(gf['n_pop'].iloc[0] == 1), 'rows': rows}
                b = bridge.get(e); gp = grid.get(b) if b else None
                nm = str(ge['emd_name'].iloc[0]) if ge['emd_name'].notna().any() else e
                emd_out[e] = {'name': nm.split()[-1] if ' ' in nm else nm, 'name_full': nm, 'bnd': b, 'touch': int(mem[(mem['emd8'] == e)].shape[0]),
                              'grid': ({'s': gp.get('s'), 'lo': gp.get('lo'), 'hi': gp.get('hi')} if gp else None), 'by_filter': by_f}
            f3 = g[g['min_area_m2'] == 66667]
            cell_out['sgg'][s] = {'n_emd': int(mem[mem['sgg'] == s]['emd8'].nunique()), 'n_emd_3mw': int(f3['emd8'].nunique()), 'n_emd_single_3mw': int(f3.loc[f3['n_pop'] == 1, 'emd8'].nunique()), 'emd': emd_out}
        rec['cells'][cell] = cell_out
        index['cells'][cell] = {'n_sgg': len(cell_out['sgg']), 'n_emd': int(mem['emd8'].nunique()), 'membership_rows': int(len(mem)), 'cross_emd_cc': int((mem.drop_duplicates('cc_id')['n_emd_of_cluster'] >= 2).sum()),
                                'by_filter': st.get('by_filter'), 'self_check': st['self_check_sgg_as_one_emd']['PASS'], 'engine_built_at': st.get('built_at'), 'sha1': st.get('sha1'), 'n_rows_id_not_in_recommend_cc_pop': n_missing_id}
        print(f"  {cell}: 시군 {len(cell_out['sgg'])} · 읍면동 {index['cells'][cell]['n_emd']:,} · 3MW frontier unique {st['by_filter']['3']['frontier_unique_cc']:,} (시군 {st['by_filter']['3']['sgg_frontier_unique_cc']:,}) · id 미실재 {n_missing_id}")
        if n_missing_id: raise SystemExit(f'거부: {cell} — recommend_cc_v4 pop 에 없는 cc id {n_missing_id} 건(export_cand_v4 먼저 재실행)')
    index['code_bridge'] = stats
    with gzip.open(out_p, 'wt', encoding='utf-8') as f: json.dump(rec, f, ensure_ascii=False, separators=(',', ':'))
    json.dump(index, open(os.path.join(a.site, 'data_v4', 'emd_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"→ {out_p} ({os.path.getsize(out_p) / 1e6:.2f} MB) · 칸 {len(rec['cells'])}")


if __name__ == '__main__':
    main()
