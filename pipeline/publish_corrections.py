# -*- coding: utf-8 -*-
"""비농지 정정 반영 뒤 사이트 부분 갱신 (ADR-0061 · 빠른 경로) — model/stages/v11_04_apply_corrections.py 다음에 돌린다.

입력: v11_04 가 남긴 <arch>/changes.json(런별 바뀐 시군) · <arch>/relabel/<run>.parquet(구성이 같은 후보의 옛 번호 → 새 번호)
  1) 수치 — 전국 값이 바뀌므로 전량(질의 한 번 읽기 · ADR-0061 이라 빠르다). 서로 독립이라 동시에 돌린다.
  2) TOP 10 — 바뀐 시군만 다시 계산, 나머지 시군 파일은 번호만 바꿔 쓴다
  3) 조건별 지도 도형 — 바뀐 시군 파일만 지우고 다시 만든다, 나머지는 번호만 바꿔 쓴다 · 압축 · 색인
  4) 후보 공간 도형(units) 전량 · 대규모 후보 산단
  5) 자문 — 경기도 시군이 바뀌면 경기연구원 자료, KEI 대상지가 바뀌면 방법 비교, 전국 지표·그림은 늘
  6) 관문 site_gate · check_js
사용: python pipeline/publish_corrections.py <arch> [시작 단계 1–6 — 끊긴 뒤 이어 돌리기]
"""
import os, sys, json, glob, gzip, time, subprocess
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import SITE, OUT, CLUSTERS, MODEL, LR   # gzip 결정성도 여기서 켜진다
RUNS_DIR = os.path.join(LR, 'scenario_runs')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd

PY = sys.executable
PIPE = os.path.join(SITE, 'pipeline')
T0 = time.time()
say = lambda *a: print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)
POLICY = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB', 'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
CELLS = POLICY + [c + '@all' for c in POLICY]


def run(rel, *args):
    t = time.time()
    r = subprocess.run([PY, os.path.join(PIPE, rel), *args], cwd=SITE, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if r.returncode != 0:
        print(r.stdout[-2500:], r.stderr[-2500:], flush=True)
        raise SystemExit(f'실패: {rel}')
    return rel, time.time() - t


def main():
    arch = sys.argv[1]
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1     # 이어 돌리기: 이 단계 번호부터(끊긴 뒤 재시작용)
    ch = json.load(open(os.path.join(arch, 'changes.json'), encoding='utf-8'))
    maps = {}
    for c in CELLS:
        p = os.path.join(arch, 'relabel', f'{c}.parquet')
        if os.path.exists(p):
            m = pd.read_parquet(p); maps[c] = dict(zip(m['old_lab'].astype(int), m['new_lab'].astype(int)))
    sg_cell = {c: set(ch['runs'].get(c, {}).get('changed_sgg', [])) for c in CELLS}
    sg_top10 = set().union(*[sg_cell[c] for c in POLICY])
    say(f"바뀐 시군 — TOP 10 {len(sg_top10)} · 지도 도형 {sum(len(v) for v in sg_cell.values())}칸")

    # 1) 수치 — 동시에
    NUM = ['export/export_v4.py', 'export/export_results_v4.py', 'export/export_narrative_v4.py', 'export/export_decree_v4.py',
           'export/export_estimate_v4.py', 'export/export_pnu_v4.py', 'export/export_parcels_v4.py', 'export/export_existing_v4.py',
           'export/export_nonfarm_v1.py',
           'export/export_grid_v4.py', 'export/export_ind_firms.py']   # 이 둘은 내용이 그대로지만 관문이 summary 보다 하루 넘게 오래된 파일을 막는다(2026-10-21)
    if start <= 1:
        with ThreadPoolExecutor(2) as ex:   # 수치 export 하나가 4–5 GB — RAM 16 GB 에서 둘까지(2026-10-20 리소스 부족 사고)
            for rel, dt in ex.map(run, NUM):
                say(f'1) {rel} {dt:.0f}s')
        say('1) {} {:.0f}s'.format(*run('export/export_big_sgg_v4.py')))       # narrative·results 와 대조하므로 그 뒤

    # 2) TOP 10 (번호 바꿔 쓰기가 들어 있어 두 번 돌리면 안 된다 — 끝났으면 3 부터 이어 돌린다)
    if start <= 2:
        args = ['--sgg', ','.join(sorted(sg_top10)) or 'none', '--relabel-dir', os.path.join(arch, 'relabel')]
        say('2) {} {:.0f}s'.format(*run('export/export_top10_v4.py', *args)))

    # 3) 조건별 지도 도형 — 다시 돌려도 안전하게.
    #   '이미 끝남' = 파일이 그 런 산출(members.parquet)보다 나중에 쓰였다. 번호가 고정(ADR-0061)이라 번호만으로는
    #   구성이 바뀐 후보를 가려낼 수 없다(2026-10-21 수정 — 처음 판은 번호로 판정했다).
    #   아니면: 바뀐 시군 파일은 지우고(다시 만듦) · 나머지는 번호 대응이 항등이 아니면 번호만 바꿔 쓴다.
    n_del = n_rl = n_ok = 0
    for c in (CELLS if start <= 3 else []):
        mm = maps.get(c, {})
        ident = all(k == v for k, v in mm.items())
        t_run = os.path.getmtime(os.path.join(RUNS_DIR, c, 'members.parquet'))
        for fp in glob.glob(os.path.join(CLUSTERS, f'*_{c}.json.gz')):
            sgg = os.path.basename(fp).split('_', 1)[0]
            if os.path.getmtime(fp) >= t_run:
                n_ok += 1; continue
            if sgg in sg_cell[c]:
                os.remove(fp); n_del += 1; continue
            if ident:
                n_ok += 1; continue
            d = json.load(gzip.open(fp, 'rt', encoding='utf-8'))
            if not all(int(f['properties']['id']) in mm for f in d['features']):
                raise SystemExit(f'중단: {os.path.basename(fp)} 번호가 대응표에 없다 — 확인 필요')
            for f in d['features']:
                f['properties']['id'] = mm[int(f['properties']['id'])]
            with gzip.open(fp + '.tmp', 'wb', compresslevel=9) as z:
                z.write(json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            os.replace(fp + '.tmp', fp); n_rl += 1
    say(f'3) 지도 도형 — 다시 만들 파일 {n_del} · 번호만 바꾼 파일 {n_rl} · 이미 끝남·그대로 {n_ok}')
    if n_del > 400:   # 정본 규칙이 바뀌어 거의 전국을 다시 그릴 때 — 두 몫을 동시에(파일 단위 체크포인트라 겹치지 않음)
        t = time.time()
        ps = [subprocess.Popen([PY, os.path.join(PIPE, 'geom/export_clusters_v4.py')], cwd=SITE,
                               env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'AGV_SHARD': f'{k}/2'},
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace') for k in (0, 1)]
        errs = [p_.communicate()[1] for p_ in ps]
        if any(p_.returncode for p_ in ps):
            print(*[e[-2000:] for e in errs], flush=True)
            raise SystemExit('실패: export_clusters_v4 (몫 실행) — 다시 돌리면 만든 파일은 건너뛴다')
        say(f'3) 지도 도형 두 몫 {time.time() - t:.0f}s')
    for rel in (('geom/export_clusters_v4.py', 'geom/compress_clusters.py') if start <= 3 else ()):
        say('3) {} {:.0f}s'.format(*run(rel)))

    # 4) 후보 공간 도형 · 대규모 후보 산단
    for rel in (('geom/export_units_v4.py', 'export/export_big_ind_near_v4.py') if start <= 4 else ()):
        say('4) {} {:.0f}s'.format(*run(rel)))

    # 5) 자문
    if start <= 5:
        _advisory(sg_cell)

    # 6) 관문
    for rel in ('gate/site_gate.py', 'gate/check_js.py'):
        run(rel); say(f'6) {rel} 통과')
    say('완료')


def _advisory(sg_cell):
    gg = any(s.startswith('41') for s in sg_cell['R2_promo'] | sg_cell['R0_current'] | sg_cell['R3_zone_all'])
    if gg:
        for rel in ('export/build_advisory_all_v1.py', 'export/export_advisory_v4.py'):
            say('5) {} {:.0f}s'.format(*run(rel)))
        say('5) 경기도 시군이 바뀌었다 — 경기연구원 저장소 동기화 필요(sync_advisory_gg.py) · 검토 사례 번호 확인')
    sa = {a['sgg'] for a in json.load(open(os.path.join(SITE, 'docs', 'method_advisory', 'study_areas.json'), encoding='utf-8'))['areas']}
    kei = sorted(sa & sg_cell['R2_promo'])
    say('5) {} {:.0f}s'.format(*run('export/export_existing_parcels_v4.py')))
    if kei:   # 대상지가 바뀌면 10곳 전부 다시(이 스크립트는 지정 시군만 돌리면 CSV 를 그 행으로 덮어쓴다)
        r = subprocess.run([PY, os.path.join(MODEL, 'proposals', 'pr0042', 'rerun_sites_20261007.py')], cwd=SITE)
        if r.returncode:
            raise SystemExit('실패: rerun_sites')
        say('5) {} {:.0f}s'.format(*run('../docs/method_advisory/add_1mw_to_comparison.py')))
        say(f'5) KEI 방법 비교 다시 — 바뀐 대상지 {kei}')
    for rel in ('../docs/method_advisory/compute_metrics_current.py', '../docs/method_advisory/make_figures.py'):
        say('5) {} {:.0f}s'.format(*run(rel)))
    say('5) KEI 문서·화면의 숫자(METHOD_ADVISORY.md · cluster_advisory.html · STUDY_AREAS.md)는 CSV 와 대조해 고친다')



if __name__ == '__main__':
    main()
