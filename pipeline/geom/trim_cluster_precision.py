# -*- coding: utf-8 -*-
"""구획 GeoJSON 좌표 표기 자릿수 정리 — 이미 양자화된 정밀도에 맞춰 소수 자리만 자른다.

왜 필요한가: export_clusters_v4 는 투영좌표(EPSG:5186)에서 위상 인식 양자화
(shapely.set_precision, 0.5 m 격자)를 한다. 그런데 4326(도 단위)으로 바꿔 JSON 으로 쓰면
`127.12345678901234` 같은 긴 실수가 그대로 찍힌다 — 이미 0.5 m 격자에 붙어 있는 점인데
표기만 17자리인 셈이라, 용량의 절반이 의미 없는 자릿수다(실측 394 MB).

왜 안전한가: 위도 1e-6도 ≈ 0.11 m 로, **이미 적용된 0.5 m 양자화보다 다섯 배 촘촘하다**.
즉 자르는 폭이 격자 간격보다 작아 서로 다른 꼭짓점이 같은 값으로 붙지 않는다.
인수인계 §7 이 경고한 사고는 소수 4자리(≈10 m)로 자른 경우다 — 그건 격자보다 20배 굵어
얇은 구획이 자기교차로 무효가 됐다. 방향이 반대다.

검증: 자른 뒤 폴리곤을 되읽어 무효 개수를 세고, 0이 아니면 그 파일을 되돌린다.
사용: python pipeline/geom/trim_cluster_precision.py [--dp 6]
"""
import os, sys, json, gzip, glob, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import shapely
from shapely.geometry import shape

CL = CLUSTERS


def rnd(cc, dp):
    if isinstance(cc[0], (list, tuple)):
        return [rnd(x, dp) for x in cc]
    return [round(cc[0], dp), round(cc[1], dp)]


def main(dp):
    fs = sorted(glob.glob(os.path.join(CL, '*.json.gz')))
    before = after = 0
    n_invalid_file = 0
    reverted = []
    for i, fp in enumerate(fs, 1):
        raw = gzip.open(fp, 'rb').read()
        before += os.path.getsize(fp)
        d = json.loads(raw.decode('utf-8'))
        bad = 0
        for f in d['features']:
            g0 = f['geometry']
            f['geometry'] = {'type': g0['type'], 'coordinates': rnd(g0['coordinates'], dp)}
            try:
                if not shape(f['geometry']).is_valid:
                    bad += 1
            except Exception:
                bad += 1
        if bad:
            # 자르면서 무효가 생기면 그 파일은 손대지 않는다 — 용량보다 형태가 먼저다
            n_invalid_file += 1
            reverted.append(os.path.basename(fp))
            after += os.path.getsize(fp)
            continue
        out = json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        with gzip.open(fp + '.tmp', 'wb', compresslevel=9) as z:
            z.write(out)
        os.replace(fp + '.tmp', fp)
        after += os.path.getsize(fp)
        if i % 300 == 0 or i == len(fs):
            print(f"  [{i}/{len(fs)}] {before/1e6:,.0f} → {after/1e6:,.0f} MB", flush=True)
    print(f"완료: {len(fs)}파일 · 소수 {dp}자리 · {before/1e6:,.1f} → {after/1e6:,.1f} MB")
    if reverted:
        print(f"  ※ 무효 발생으로 되돌린 파일 {n_invalid_file}: {', '.join(reverted[:5])}"
              f"{' …' if len(reverted) > 5 else ''}")
    else:
        print("  무효 발생 0 — 모든 파일에 적용")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dp', type=int, default=6,
                    help='소수 자릿수 (기본 6 ≈ 0.11m — 상류 양자화 0.5m 보다 촘촘해야 안전)')
    main(ap.parse_args().dp)
