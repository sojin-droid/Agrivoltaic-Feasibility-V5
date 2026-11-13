# -*- coding: utf-8 -*-
"""읍면동 경계(grid_emd.json.gz)에 현행 시군 코드 'g' 를 붙인다 — 화면이 경계를 시군에 귀속할 때 쓰는 값.

왜: 경계(V-World LT_C_ADEMD)는 2026 신 코드를 쓴다(광주·전남 통합 '12', 인천 구 신설, 화성 구 신설).
화면은 코드 앞 5자리로 시군을 맞춰 왔는데, 신 코드는 시군 접미가 현행 코드와 대응하지 않아(예: 12790 = 해남, 46790 = 화순)
914개 읍면동이 시군에 붙지 않았고, 그 시군의 지도에 읍면동 경계가 그려지지 않았다(2026-11-13 영광군 확인).

방법(발행 자료만 읽음, 새 산정 없음):
  · 앞 5자리가 sgg_matrix 시군 코드면 그대로.
  · 아니면 신 시군 코드(앞 5자리) 단위로, 소속 읍면동 이름을 bjd_v4(법정동 코드표, 현행 시군 코드)의 읍면동 이름과 대조해
    표를 모은다(같은 시도만: 신 '12' → 구 '46'·'29'). 최다 득표 시군이 소속 읍면동의 80% 이상이고 2위의 2배 이상일 때만 연결한다.
  · 조건을 못 넘으면 연결하지 않고(null) 보고한다 — 숨은 귀속 금지.
사용: python pipeline/export/patch_emd_sgg.py   (export_grid_v4.py 끝에서도 호출)
"""
import os, sys, json, gzip, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import OUT   # gzip 저장 시각 0 고정(ADR-0061)도 여기서 걸린다

SIDO_BRIDGE = {'12': ('46', '29')}   # 신 시도코드 → 구 시도코드
MIN_SHARE, MIN_LEAD = 0.8, 2.0


def main():
    fo = os.path.join(OUT, 'grid_emd.json.gz')
    fc = json.load(gzip.open(fo))
    codes = json.load(open(os.path.join(OUT, 'sgg_matrix.json'), encoding='utf-8'))['codes']
    rows = json.load(gzip.open(os.path.join(OUT, 'bjd_v4.json.gz')))['rows']
    by_name = collections.defaultdict(set)
    for code, nm in rows:
        for tok in nm.split()[1:]:
            by_name[tok].add(code[:5])

    feats = fc['features']
    groups = collections.defaultdict(list)
    for f in feats:
        c5 = f['properties']['c'][:5]
        if c5 not in codes:
            groups[c5].append(f['properties']['n'])

    bridge, report = {}, []
    for new5, names in sorted(groups.items()):
        allow = SIDO_BRIDGE.get(new5[:2], (new5[:2],))
        votes = collections.Counter()
        for n in names:
            for s5 in by_name.get(n, ()):
                if s5[:2] in allow and s5 in codes:
                    votes[s5] += 1
        top = votes.most_common(2)
        ok = bool(top) and top[0][1] >= MIN_SHARE * len(names) and (len(top) < 2 or top[0][1] >= MIN_LEAD * top[1][1])
        if ok:
            bridge[new5] = top[0][0]
        report.append((new5, len(names), top, top[0][0] if ok else None))

    n_direct = n_bridged = n_none = 0
    for f in feats:
        p = f['properties']; c5 = p['c'][:5]
        if c5 in codes:
            p['g'] = c5; n_direct += 1
        elif c5 in bridge:
            p['g'] = bridge[c5]; n_bridged += 1
        else:
            p['g'] = None; n_none += 1

    raw = json.dumps(fc, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    with gzip.open(fo + '.tmp', 'wb', compresslevel=9) as z:
        z.write(raw)
    os.replace(fo + '.tmp', fo)

    for new5, n, top, to in report:
        nm = codes[to]['name'] if to else '연결 안 함'
        print(f"  {new5} 읍면동 {n:>3} → {to or '-':>5} {nm}  표 {top}")
    print(f"grid_emd 시군 귀속: 직접 {n_direct:,} · 신 코드 연결 {n_bridged:,} · 미연결 {n_none:,} (전체 {len(feats):,})")


if __name__ == '__main__':
    main()
