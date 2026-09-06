# -*- coding: utf-8 -*-
"""발행 — 정본에서 화면까지 한 줄로. 순서를 사람이 아니라 이 파일이 안다.

왜 필요한가: export 스크립트가 열두 개고, 순서가 틀리면 조용히 어긋난 자산이 나온다.
실제로 구획 색인이 압축된 정본을 못 읽어 통째로 빠질 뻔했고(2026-08-30), 그건
"압축은 색인 뒤에" 라는 순서를 사람이 기억해야 했기 때문이다.

단계
  1 수치   export/*.py        정본 질의 → data_v4/*.json
  2 지오   geom/*.py          구획 폴리곤 → data_v4/clusters/ (오래 걸림)
  3 관문   gate/site_gate.py  FAIL 이면 여기서 멈춘다 — 어긋난 값은 발행되지 않는다
  4 커밋   git commit         (--commit 을 준 경우에만)

사용
  python publish.py                 # 수치만 (지오메트리는 건너뜀 — 빠름)
  python publish.py --geom          # 구획까지 다시 굽는다 (수십 분)
  python publish.py --gate-only     # 관문만
  python publish.py --commit "메시지"
push 는 하지 않는다 — 바깥으로 나가는 일은 사람이 누른다.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.join(HERE, 'pipeline')
PY = sys.executable

# 수치 — 서로 독립이라 순서는 읽기 좋은 순
NUM = ['export_v4.py', 'export_results_v4.py', 'export_narrative_v4.py',
       'export_insights_v4.py', 'export_grid_v4.py', 'export_ind_firms.py',
       'export_stage_v4.py', 'export_decree_v4.py']

# 지오메트리 — **순서가 뜻을 갖는다**
#   export_clusters_v4 가 끝에 rebuild_cluster_index 를 부른다(걸침 표시 + 색인).
#   압축은 그 다음이어야 한다 — 먼저 압축하면 색인 단계가 .json 을 못 찾는다.
GEOM = ['export_clusters_v4.py', 'compress_clusters.py']


def run(rel, layer):
    fp = os.path.join(PIPE, layer, rel)
    t0 = time.time()
    print(f"\n── {layer}/{rel}", flush=True)
    r = subprocess.run([PY, fp], cwd=HERE)
    if r.returncode != 0:
        raise SystemExit(f"중단: {layer}/{rel} 실패 (코드 {r.returncode})")
    print(f"   {time.time() - t0:,.0f}초", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--geom', action='store_true', help='구획 폴리곤까지 다시 굽는다')
    ap.add_argument('--gate-only', action='store_true', help='관문만 돌린다')
    ap.add_argument('--commit', metavar='메시지', help='관문 통과 시 커밋한다')
    a = ap.parse_args()

    t0 = time.time()
    if not a.gate_only:
        for f in NUM:
            run(f, 'export')
        if a.geom:
            for f in GEOM:
                run(f, 'geom')
        else:
            print("\n(지오메트리 건너뜀 — 구획을 다시 구우려면 --geom)", flush=True)

    print("\n── gate/site_gate.py", flush=True)
    g = subprocess.run([PY, os.path.join(PIPE, 'gate', 'site_gate.py')], cwd=HERE)
    if g.returncode != 0:
        raise SystemExit("중단: 관문 FAIL — 발행하지 않는다")

    if a.commit:
        subprocess.run(['git', 'add', '-A'], cwd=HERE, check=True)
        subprocess.run(['git', 'commit', '-m', a.commit], cwd=HERE, check=True)
        print("커밋 완료 — push 는 직접 (git push origin main)", flush=True)

    print(f"\n발행 준비 완료 — 전체 {time.time() - t0:,.0f}초", flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
