# -*- coding: utf-8 -*-
"""[폐지 2026-08-29] 소유 필터(CP) 구획 지도 export — 더 이상 쓰지 않는다.

ADR-0040 으로 **소유 필터가 정본 우주로 승격**됐다. 즉 R0_current·R2_promo 등 정본 런이
곧 구 CP 이고, export_clusters_v4.py 가 그 지도를 이미 낸다. 구 파일명
({sgg}_SOFT_R2_CP.json.gz)은 없어졌으므로 이 스크립트를 돌리면 두 세대가 섞인다(제3조).

  구 SOFT_R2_CP    -> R2_promo
  구 SOFT_R2_CP_SB -> R2_promo_SB
  구 ANCHOR_CP     -> R0_current
  구 ANCHOR_CP_SB  -> R0_current_SB

대체: python pipeline/export_clusters_v4.py   (정본 8칸 · 연접 구획 전량)

파일을 지우지 않고 실행만 막는다 — 구 본문은 git 이력(c26caff)에 있다.
"""
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print("거부: 폐지된 스크립트다 (ADR-0040 — 소유 필터가 정본 우주로 승격).")
print("      대체: python pipeline/export_clusters_v4.py")
print("      구 CP 칸 대응: SOFT_R2_CP->R2_promo · ANCHOR_CP->R0_current · *_CP_SB->*_SB")
raise SystemExit(1)
