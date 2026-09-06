# -*- coding: utf-8 -*-
"""경로 한 곳 — 스크립트가 어느 층에 있든 같은 뿌리를 가리킨다.

층을 나누고 나면 `os.path.dirname` 을 몇 번 하느냐가 파일마다 달라진다. 그 계산을
각자 하게 두면 파일을 옮길 때마다 조용히 어긋나고, 어긋난 채로도 실행은 되어서
엉뚱한 자리에 파일을 쓴다. 그래서 표식(data_v4)을 찾아 올라가 한 번만 정한다.
"""
import os

ROOT = r"C:\Users\user\새 폴더"              # 자료 뿌리(로컬 — 저장소 밖)
MODEL = os.path.join(ROOT, "model")            # 정본 모델 — 값의 출처
LR = os.path.join(ROOT, "Ledger_Rebuild")      # 원장·런 산출
CAD = os.path.join(ROOT, "Cadastre_All")       # 지적 폴리곤


def _root(start):
    d = os.path.dirname(os.path.abspath(start))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, 'data_v4')):
            return d
        p = os.path.dirname(d)
        if p == d:
            break
        d = p
    raise SystemExit('발행 저장소 뿌리를 찾지 못했다 — data_v4 가 있는 상위 폴더가 없다')


SITE = _root(__file__)
OUT = os.path.join(SITE, 'data_v4')
CLUSTERS = os.path.join(OUT, 'clusters')
