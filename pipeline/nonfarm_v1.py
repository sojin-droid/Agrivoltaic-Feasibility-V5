# -*- coding: utf-8 -*-
"""비농지 제외(자동 + 위성사진 육안 검토) 검토 고정본 — 검토 결과 통계(export_nonfarm_v1 → nonfarm.html)만 읽는다.
값 반영(면적·MW·지도)은 정본이 한다 — model ADR-0060(nonfarm_keep_v1 · VIEW elig_v2nf). 여기서는 사이트 값을 바꾸지 않는다.

원천: Ledger_Rebuild/experiments/nonfarm_review/freeze_v1.py 산출
  nonfarm_review_v1.parquet  후보별 a0/a_final(㎡ · 대장 면적 기준)·mw0/mw_final·검토 여부·판정·사유별 제외 면적
  nonfarm_final_v1.gpkg      후보별 최종 남은 땅(EPSG:5186) — 뺀 필지를 지운 모양
대상: R2_promo(농업진흥구역 개방 · 법인·국공유) 1MW 이상 후보 공간 5,645곳 — 후보 번호(lab)는 비농지 제외 전(검토 당시) 번호다.
"""
import os
import pandas as pd
from paths import NF

RUN = 'R2_promo'
TBL = os.path.join(NF, 'nonfarm_review_v1.parquet')
GEO = os.path.join(NF, 'nonfarm_final_v1.gpkg')


def table():
    """검토 당시 lab → 행."""
    t = pd.read_parquet(TBL)
    return t.set_index('lab')
