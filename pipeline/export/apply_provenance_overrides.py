# -*- coding: utf-8 -*-
"""사람이 확인한 출처 값(provenance_overrides.json)을 provenance 행에 덮어쓴다 (2026-10-14).

provenance_v1(DB)은 원천 기록에 없는 값을 unknown 으로 둔다. 기록 밖에서 확인한 값은 DB 를 고칠 수 있는
PC(자료 뿌리 AGRI_ROOT)가 아니어도 반영돼야 해서, 근거를 단 덮어쓰기 표를 저장소에 두고 두 곳에서 쓴다.
  · export_existing_v4.py — DB 에서 provenance_v4.json 을 다시 낼 때 apply_rows() 로 덮어쓴다
  · 이 파일을 직접 실행 — 이미 내보낸 data_v4/provenance_v4.json 과 data_v4/advisory/gg_v1.json.gz 의
    provenance 를 그 자리에서 고친다(원장·런 산출이 없는 PC 에서도 된다)
덮어쓴 행에는 override_evidence 칸에 근거를 남긴다. 표에 없는 칸은 DB 값을 그대로 둔다.
사용: python pipeline/export/apply_provenance_overrides.py
"""
import os, sys, json, gzip

HERE = os.path.dirname(os.path.abspath(__file__))
OVR = os.path.join(HERE, 'provenance_overrides.json')
EV = 'override_evidence'
ADV_EXTRA = ['raw:slope']      # 자문 자산 provenance 에 2026-10-14 더한 id (export_advisory_v4.PROV_IDS 와 맞춘다)


def load():
    return json.load(open(OVR, encoding='utf-8'))['rows']


def apply_rows(cols, rows, ovr=None):
    """(cols, rows) → (cols, rows). 없는 dataset_id 는 새 행으로 더한다(나머지 칸 unknown)."""
    ovr = load() if ovr is None else ovr
    cols = list(cols) + ([EV] if EV not in cols else [])
    out, seen = [], set()
    for r in rows:
        d = dict(zip(cols, list(r) + [None] * (len(cols) - len(r))))
        o = ovr.get(d['dataset_id'])
        if o:
            d.update({k: v for k, v in o.items() if k != 'evidence' and k in cols}); d[EV] = o.get('evidence')
        out.append([d[c] for c in cols]); seen.add(d['dataset_id'])
    for k, o in ovr.items():
        if k in seen:
            continue
        d = {c: 'unknown' for c in cols}; d['dataset_id'] = k; d['is_canon'] = False
        d.update({c: v for c, v in o.items() if c != 'evidence' and c in cols}); d[EV] = o.get('evidence')
        out.append([d[c] for c in cols])
    out.sort(key=lambda r: r[0])
    return cols, out


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(HERE))
    from paths import OUT
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ovr = load()
    pp = os.path.join(OUT, 'provenance_v4.json')
    P = json.load(open(pp, encoding='utf-8'))
    P['cols'], P['rows'] = apply_rows(P['cols'], P['rows'], ovr)
    P['overrides'] = 'pipeline/export/provenance_overrides.json — 기록 밖에서 확인한 값(행마다 override_evidence)'
    json.dump(P, open(pp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f"provenance_v4: {len(P['rows'])} datasets · 덮어쓴 행 {sum(1 for r in P['rows'] if r[0] in ovr)}")
    # 자문 자산의 provenance 는 provenance_v4 에서 고른 dict — 같은 id 를 새 값으로 바꾼다(다른 값은 손대지 않는다)
    gp = os.path.join(OUT, 'advisory', 'gg_v1.json.gz')
    G = json.load(gzip.open(gp, 'rt', encoding='utf-8'))
    by = {r[0]: dict(zip(P['cols'], r)) for r in P['rows']}
    G['provenance'] = {k: by.get(k, v) for k, v in G['provenance'].items()}
    G['provenance'].update({k: by[k] for k in ADV_EXTRA if k in by})     # export_advisory_v4 PROV_IDS 에 새로 넣은 id
    G['provenance_overrides'] = P['overrides']
    with gzip.open(gp, 'wt', encoding='utf-8') as fo:
        json.dump(G, fo, ensure_ascii=False, separators=(',', ':'))
    print(f"advisory/gg_v1: provenance {len(G['provenance'])}건 갱신")
