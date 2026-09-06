# -*- coding: utf-8 -*-
"""구획 색인 재작성 + 경계 걸침(sp) 표시 — **압축본(.json.gz)도 읽는다**.

왜 따로 두는가: export_clusters_v4 의 색인 단계가 `{sgg}_{cell}.json` 만 찾았다.
정본은 이미 압축(.json.gz)돼 있어 그 단계에서 통째로 빠지고, 색인에 대조군만 남는다.
지도는 `idx.sgg[c]` 로 시군 존재 여부를 판정하므로 색인이 빠지면 화면이 통째로 빈다.
그래서 색인 작성은 확장자에 무관한 별도 단계로 분리한다(한 곳에서만 만든다).

사용: python pipeline/geom/rebuild_cluster_index.py
"""
import os, sys, io, json, gzip, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd

LR = os.path.join(ROOT, 'Ledger_Rebuild')
RUNS = os.path.join(LR, 'scenario_runs')
OUT = CLUSTERS

CELLS_MAIN = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB',
              'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
CELLS = CELLS_MAIN + [c + '@all' for c in CELLS_MAIN]
GEN = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def load(fp):
    """.json / .json.gz 어느 쪽이든 읽는다. 없으면 None."""
    if os.path.exists(fp):
        return json.load(io.open(fp, encoding='utf-8')), fp, False
    if os.path.exists(fp + '.gz'):
        return json.loads(gzip.open(fp + '.gz', 'rb').read().decode('utf-8')), fp + '.gz', True
    return None, None, None


def save(d, path, gz):
    tmp = path + '.tmp'
    b = json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if gz:
        with gzip.open(tmp, 'wb', compresslevel=9) as z:
            z.write(b)
    else:
        io.open(tmp, 'wb').write(b)
    os.replace(tmp, path)


nodes = pd.read_parquet(os.path.join(LR, 'engine_cache', 'nodes.parquet'),
                        columns=['pnu', 'area'])
area = pd.Series(nodes['area'].values, index=nodes['pnu'].values)
del nodes

span, comp_area = {}, {}
for c in CELLS:
    m = pd.read_parquet(os.path.join(RUNS, c, 'members.parquet'), columns=['pnu', 'lab'])
    m['sgg'] = m['pnu'].str[:5]
    m['a'] = area.reindex(m['pnu'].values).values
    comp_area[c] = m.groupby('lab')['a'].sum() / 1e6
    span[c] = set(m.groupby('lab')['sgg'].nunique().pipe(lambda s: s[s > 1]).index)
    print(f"{c}: 구획 {m['lab'].nunique():,} · 걸침 {len(span[c]):,}", flush=True)

sggs = sorted({os.path.basename(p).split('_')[0]
               for p in glob.glob(os.path.join(OUT, '*.json*'))})
print(f"파일에 있는 시군 {len(sggs)}", flush=True)

index = {'generated': GEN, 'cells': CELLS, 'sgg': {}}
rewrote = 0
for i, sgg in enumerate(sggs, 1):
    ent = {}
    for c in CELLS:
        d, path, gz = load(os.path.join(OUT, f'{sgg}_{c}.json'))
        if d is None:
            continue
        changed = False
        for f in d['features']:
            sp = 1 if f['properties']['id'] in span[c] else 0
            if f['properties'].get('sp', None) != sp:
                f['properties']['sp'] = sp
                changed = True
        if changed:
            save(d, path, gz)
            rewrote += 1
        ids = {f['properties']['id'] for f in d['features']}
        ent[c] = {'k': len(ids),
                  'km2': round(float(comp_area[c].reindex(list(ids)).sum()), 1)}
    index['sgg'][sgg] = ent
    if i % 25 == 0 or i == len(sggs):
        print(f"  [{i}/{len(sggs)}]", flush=True)

fo = os.path.join(SITE, 'data_v4', 'clusters_index.json')
json.dump(index, io.open(fo, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
miss = [c for c in CELLS if not any(c in e for e in index['sgg'].values())]
print(f"색인 {len(index['sgg'])}시군 · sp 갱신 {rewrote}파일 · {GEN}")
print('빠진 칸: ' + (', '.join(miss) if miss else '없음'))
