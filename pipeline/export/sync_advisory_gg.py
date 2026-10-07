# -*- coding: utf-8 -*-
"""경기연구원 자문 정적 패키지 동기화 — V5 저장소의 자문 자산을 별도 공개 저장소(agrivoltaic-advisory-gg)에 바이트 동일 복사.

대상 파일 = 저장소의 PACKAGE_MANIFEST.json 'files' 목록(경로는 두 저장소에서 같다) + 새로 생긴 data_v4/advisory/* 파일.
복사 후 manifest 의 sha256·bytes 를 다시 적고 revision 문구를 남긴다. push 는 하지 않는다(사람이 확인 뒤).
사용: python pipeline/export/sync_advisory_gg.py "r16 2026-10-07: ..."
"""
import os, sys, json, glob, hashlib, shutil, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GG = r'C:\Users\user\agrivoltaic-advisory-gg'
rev = sys.argv[1] if len(sys.argv) > 1 else f'sync {datetime.date.today().isoformat()}'
mp = os.path.join(GG, 'PACKAGE_MANIFEST.json'); man = json.load(open(mp, encoding='utf-8'))
files = set(man['files'].keys())
for p in glob.glob(os.path.join(SITE, 'data_v4', 'advisory', '**', '*'), recursive=True):
    if os.path.isfile(p): files.add(os.path.relpath(p, SITE).replace(os.sep, '/'))
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()
changed, missing = [], []
for rel in sorted(files):
    src = os.path.join(SITE, rel); dst = os.path.join(GG, rel)
    if not os.path.exists(src): missing.append(rel); continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    before = sha(dst) if os.path.exists(dst) else None; s = sha(src)
    if before != s: shutil.copy2(src, dst); changed.append(rel)
    man['files'][rel] = {'bytes': os.path.getsize(src), 'sha256': s}
man['revision'] = rev; man['source_branch'] = 'main'; man['source_state'] = f'synced {datetime.datetime.now().isoformat(timespec="minutes")}'
try:
    import subprocess; man['source_head'] = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=SITE, capture_output=True, text=True).stdout.strip()
except Exception: pass
json.dump(man, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'동기화 — 변경 {len(changed)} · 전체 {len(files)} · 원본 없음 {len(missing)}')
for c in changed[:30]: print('  ', c)
if missing: print('  ⚠ 원본 없음:', missing[:10])
