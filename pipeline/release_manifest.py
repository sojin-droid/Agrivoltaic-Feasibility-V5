# -*- coding: utf-8 -*-
"""발행 입력 상태 매니페스트 — 지금 data_v4 를 만든 입력이 정확히 무엇인지 해시로 고정한다 (감사 F-01·F-02·F-21).

왜 필요한가: 발행 저장소의 커밋만으로는 입력을 재현할 수 없다. export 는 저장소 밖의 모델 코드(model/query.py 등 — 미커밋 변경 포함)와
정본 DuckDB·런 산출물을 읽는다. 동결본(PAPER-FREEZE-001)은 2026-09-20 시점의 DB 해시를 적었고, 라이브 DB 는 그 뒤로 표가 더해져 해시가 다르다.
그 차이는 오류가 아니라 역할 차이다 — 동결본 = 논문 재현용 스냅숏, 라이브 DB = 현재 작업 DB. 여기서는 둘을 나란히 적어 섞이지 않게 한다.

무엇을 적는가 (전부 실측 — 추정값 없음)
  · 사이트 저장소: branch · HEAD · 미커밋 파일 목록
  · 모델 저장소: branch · HEAD · master · 미커밋·미추적 파일마다 sha256 (export 가 import 하는 코드가 여기 있다)
  · 정본 DuckDB: 현재 sha256 · 크기 · mtime  vs  동결 manifest 의 duckdb_sha256_20260920
  · 런 산출물(scenario_runs 8칸 × block_context/members/clusters/grid_link) sha256 과 동결본 사본 일치 여부
  · analysis_unit_v1.gpkg sha256 · 동결본 checksums.csv sha256 · 원고 sha256
  · 동결본 파일 범위: checksums.csv 등재 수 vs 폴더 전체 파일 수(등재 범위 밖은 목록으로)
  · data_v4 자산별 'generated' 값(있으면) — 언제 export 됐는지

사용: python pipeline/release_manifest.py            → release/V5.5_INPUT_MANIFEST.json 을 쓴다
      python pipeline/release_manifest.py --no-db    → DuckDB(23 GB) 해시를 건너뛴다(빠른 점검용 — 매니페스트에 skipped 로 적힌다)
"""
import os, sys, json, csv, glob, hashlib, subprocess, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import SITE, ROOT, LR, OUT
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FZ = os.path.join(LR, 'paper_freeze', 'PAPER-FREEZE-001')
RUNS = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB', 'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
RUN_FILES = ['block_context.parquet', 'block_context.json', 'members.parquet', 'clusters.parquet', 'grid_link.parquet']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def git(repo, *a):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, encoding='utf-8')
    return r.stdout.strip()


def repo_state(repo, dirty_hash=False):
    st = {'branch': git(repo, 'branch', '--show-current'), 'head': git(repo, 'rev-parse', 'HEAD')}
    por = [l for l in subprocess.run(['git', '-C', repo, 'status', '--porcelain', '-uall'], capture_output=True, text=True,
                                     encoding='utf-8').stdout.splitlines() if l.strip()]   # strip() 하면 첫 줄 상태 칸이 잘린다
    st['n_dirty'] = len(por)
    ent = []
    for l in por:
        code, path = l[:2], l[3:].strip().strip('"')
        e = {'status': code.strip(), 'path': path}
        if dirty_hash:
            fp = os.path.join(repo, path)
            e['sha256'] = sha(fp) if os.path.isfile(fp) else ('deleted' if 'D' in code else 'not-a-file')
        ent.append(e)
    st['dirty'] = ent
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-db', action='store_true')
    a = ap.parse_args()
    man = {'written_at': datetime.datetime.now().isoformat(timespec='seconds'),
           'purpose': '발행 입력 상태 고정 — 동결본(논문 재현)과 라이브 작업 DB 를 구분해 적는다. 추정값 없음.'}
    man['site_repo'] = repo_state(SITE)
    model = repo_state(ROOT, dirty_hash=True)
    model['master'] = git(ROOT, 'rev-parse', 'master')
    man['model_repo'] = model

    fzm = json.load(open(os.path.join(FZ, 'manifest.json'), encoding='utf-8'))
    snap = fzm.get('input_snapshot', {})
    db = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
    man['duckdb'] = {'role': 'live working database (현재 작업 DB — 동결 스냅숏이 아님)',
                     'path': os.path.relpath(db, ROOT).replace(os.sep, '/'),
                     'bytes': os.path.getsize(db),
                     'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(db)).isoformat(timespec='seconds'),
                     'sha256': ('skipped (--no-db)' if a.no_db else sha(db)),
                     'freeze_recorded_sha256': snap.get('duckdb_sha256_20260920'),
                     'freeze_recorded_bytes': snap.get('duckdb_bytes')}
    if not a.no_db:
        man['duckdb']['equals_freeze_snapshot'] = man['duckdb']['sha256'] == snap.get('duckdb_sha256_20260920')

    runs = {}
    for r in RUNS:
        for f in RUN_FILES:
            lp = os.path.join(LR, 'scenario_runs', r, f)
            fp = os.path.join(FZ, 'results', 'policy_16', r, f)
            if not os.path.exists(lp):
                continue
            h = sha(lp)
            runs[f'{r}/{f}'] = {'sha256': h, 'equals_freeze_copy': (os.path.exists(fp) and sha(fp) == h)}
    man['scenario_runs'] = runs
    au = os.path.join(LR, 'analysis_units', 'analysis_unit_v1.gpkg')
    man['analysis_unit_v1_gpkg'] = {'sha256': sha(au), 'bytes': os.path.getsize(au)} if os.path.exists(au) else 'missing'

    ck = os.path.join(FZ, 'checksums.csv')
    listed = {r['path'].replace(os.sep, '/') for r in csv.DictReader(open(ck, encoding='utf-8-sig'))}
    allf = []
    for dp, dn, fn in os.walk(FZ):
        for f in fn:
            allf.append(os.path.relpath(os.path.join(dp, f), FZ).replace(os.sep, '/'))
    outside = sorted(set(allf) - listed)
    tops = {}
    for p in outside:
        k = p.split('/')[0] if '/' in p else p
        tops[k] = tops.get(k, 0) + 1
    ms = os.path.join(ROOT, 'docs', 'PAPER_MANUSCRIPT_V0.2.md')
    man['freeze'] = {'id': 'PAPER-FREEZE-001', 'checksums_csv_sha256': sha(ck),
                     'n_listed': len(listed), 'n_files_in_folder': len(allf),
                     'n_not_listed': len(outside), 'not_listed_by_top_folder': tops,
                     'scope_note': 'checksums.csv 등재 범위 = results/ · inputs/ · metadata/ 의 동결 대상. rerun_A/ · rerun_B/ 는 재현 검증 작업공간(그 안의 DB 는 쓰기 가능), '
                                   'checksums.csv · manifest.json · paper_freeze_baseline.json 은 동결 자체의 기록 파일이라 자기 목록에 없다. 등재 밖 파일을 동결본에 더하지 않는다.'}
    man['manuscript'] = {'id': 'PAPER-MANUSCRIPT-FINAL-001', 'path': 'docs/PAPER_MANUSCRIPT_V0.2.md',
                         'sha256': sha(ms) if os.path.exists(ms) else 'missing',
                         'git_tracked': bool(git(ROOT, 'ls-files', 'docs/PAPER_MANUSCRIPT_V0.2.md'))}

    assets = {}
    for fp in sorted(glob.glob(os.path.join(OUT, '*.json'))):
        try:
            d = json.load(open(fp, encoding='utf-8'))
            g = d.get('generated') if isinstance(d, dict) else None
        except Exception:
            g = None
        assets[os.path.basename(fp)] = {'generated': g, 'sha256': sha(fp)}
    man['data_v4_top_level_json'] = assets

    os.makedirs(os.path.join(SITE, 'release'), exist_ok=True)
    out = os.path.join(SITE, 'release', 'V5.5_INPUT_MANIFEST.json')
    json.dump(man, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"저장 {os.path.relpath(out, SITE)} · 모델 미커밋 {model['n_dirty']} · 런 파일 {len(runs)} "
          f"(동결 사본 일치 {sum(1 for v in runs.values() if v['equals_freeze_copy'])}) · DB {man['duckdb']['sha256'][:16]}")


if __name__ == '__main__':
    main()
