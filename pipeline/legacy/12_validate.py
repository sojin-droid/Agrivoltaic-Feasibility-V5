# -*- coding: utf-8 -*-
"""12_validate.py — 원장 상설 검증 게이트 (02 재실행·원장 갱신 후 필수 통과)
=================================================================
검증 항목 (실패 시 exit 1 — 후속 단계 진행 금지):
  V1. 적격 필지 지목 화이트리스트: s0/s3 적격 집합에 전·답·과수원 외 지목 0건
      (2026-07-14 파주 검수 이슈로 상설화 — 당시 결과 0건, 재발 감시 목적)
  V2. PNU 중복 0 / 19자리 / 파일-코드 일치
  V3. 좌표 유효 범위 (한반도 bbox) + 시군 중심 35km 초과 이탈 (도서 예외: 보령)
  V4. 필수 필드 결측 0 (area/jimok/agpromo/owner/dong) + use_zone_missing 플래그 정합
  V5. slope 급경사(slope_mean>15) 미태깅 적격 0건
사용: python 12_validate.py [sgg콤마 | all]
"""
import os, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
FINAL = os.path.join(BASE, "pipeline_out", "parcels_final")
FARM = {"01", "02", "03"}
ISLAND_OK = {"44180", "46130", "46230"}  # 보령 오천면 / 여수·광양 도서 지역

def validate(sgg):
    d = pd.read_parquet(os.path.join(FINAL, f"{sgg}.parquet"))
    errs = []
    el = d[(d.s0_eligible == 1) | (d.s2_eligible == 1)]
    bad = el[~el.jimok.isin(FARM)]
    if len(bad):
        errs.append(f"V1 적격 비농지 지목 {len(bad)}건 ({bad.jimok.value_counts().head(3).to_dict()})")
    if int(d.pnu.duplicated().sum()):
        errs.append(f"V2 PNU 중복 {int(d.pnu.duplicated().sum())}")
    if int((d.pnu.str.len() != 19).sum()):
        errs.append("V2 PNU 자릿수 이상")
    if int((d.pnu.str[:5] != sgg).sum()):
        errs.append("V2 파일-코드 불일치")
    off = (d.lon < 124) | (d.lon > 132) | (d.lat < 33) | (d.lat > 39)
    if off.any():
        errs.append(f"V3 좌표 한반도 밖 {int(off.sum())}")
    mlon, mlat = d.lon.median(), d.lat.median()
    dist = np.sqrt(((d.lon - mlon) * 88.8) ** 2 + ((d.lat - mlat) * 111.0) ** 2)
    far = int((dist > 35).sum())
    if far and sgg not in ISLAND_OK:
        errs.append(f"V3 중심 35km 초과 {far}")
    for c in ["area_m2", "jimok", "agpromo_class", "owner_class", "dong_code"]:
        na = d[c].isna() if d[c].dtype != object else (d[c].isna() | d[c].astype(str).str.strip().isin(["", "nan", "None"]))
        if int(na.sum()):
            errs.append(f"V4 {c} 결측 {int(na.sum())}")
    if "use_zone_missing" in d:
        viol = d[(d.use_zone_missing == 1) & ((d.s0_eligible == 1) | (d.s2_eligible == 1))]
        if len(viol):
            errs.append(f"V4 use_zone_missing 적격 위반 {len(viol)}")
    steep = d[d.slope_mean.notna() & (d.slope_mean > 15) & (d.excl_slope15 == 0)
              & ((d.s0_eligible == 1) | (d.s2_eligible == 1))]
    if len(steep):
        errs.append(f"V5 급경사 미태깅 적격 {len(steep)}")
    return errs


def validate_scenario_summary():
    """V6 시나리오 요약 무결성 (배포 게이트, 2026-07-16) — S0·S3 동시 존재 + 값 정상범위.
    S0 유실 버그 유형(재산출이 타 시나리오 산출물 파괴) 상설 방지."""
    import json
    errs = []
    sw_path = os.path.join(BASE, "pipeline_out", "blocks_sweep_summary.json")
    if not os.path.exists(sw_path):
        return ["V6 blocks_sweep_summary.json 부재"]
    sw = json.load(open(sw_path, encoding="utf-8"))
    # V7 천안 단일 코드 고정 (2026-07-16 잠금 — 44131/44133 재분리 금지)
    if "44131" in sw or "44133" in sw:
        errs.append("V7 천안 재분리 감지 (44131/44133) — 44130 단일이어야 함")
    if "44130" not in sw:
        errs.append("V7 천안 단일 코드(44130) 부재")
    for sgg, v in sw.items():
        for scn in ("S0", "S1", "S2"):
            if scn not in v:
                errs.append(f"V6 {sgg}: {scn} 요약 유실")
                continue
            s = v[scn]
            for k in ("b_mw_t30", "seg_mw", "seg_n", "status_t30"):
                if k not in s:
                    errs.append(f"V6 {sgg}.{scn}: {k} 누락")
            # 값 범위: b ≤ seg_mw, 음수 없음, S3 ≥ S0 (진흥 포함이라 잠재 더 큼)
            if s.get("b_mw_t30", 0) < 0 or s.get("seg_mw", 0) < 0:
                errs.append(f"V6 {sgg}.{scn}: 음수 MW")
            if (s.get("b_mw_t30") or 0) > (s.get("seg_mw") or 0) + 0.1:
                errs.append(f"V6 {sgg}.{scn}: b({s.get('b_mw_t30')})>seg({s.get('seg_mw')})")
        if "S0" in v and "S2" in v:
            if (v["S2"].get("seg_mw") or 0) < (v["S0"].get("seg_mw") or 0) - 0.1:
                errs.append(f"V6 {sgg}: S2 잠재({v['S2'].get('seg_mw')})<S0({v['S0'].get('seg_mw')})")
            # S2 ⊇ S1 (자연환경 포함이 더 큼)
            if (v.get("S2",{}).get("seg_mw") or 0) < (v.get("S1",{}).get("seg_mw") or 0) - 0.1:
                errs.append(f"V6 {sgg}: S2<S1 (자연환경 포함이 더 커야)")
            st = v["S1"].get("status_t30")
            if st not in ("유력", "지정 가능", "요건 미달"):
                errs.append(f"V6 {sgg}: S1 판정값 이상 '{st}'")
    return errs


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "scenario":  # 배포 게이트 전용
        errs = validate_scenario_summary()
        if errs:
            print("[FAIL] 시나리오 요약 무결성:\n  " + "\n  ".join(errs[:30]))
            sys.exit(1)
        import json
        n = len(json.load(open(os.path.join(BASE, "pipeline_out", "blocks_sweep_summary.json"), encoding="utf-8")))
        print(f"[PASS] V6 시나리오 요약 무결성 — {n}개 코드 S0·S3 동시 존재·정상범위")
        sys.exit(0)
    sggs = ([os.path.basename(f)[:5] for f in sorted(glob.glob(os.path.join(FINAL, "*.parquet")))]
            if arg == "all" else arg.split(","))
    fail = 0
    for s in sggs:
        errs = validate(s)
        if errs:
            fail += 1
            print(f"[FAIL] {s}: " + " / ".join(errs))
        else:
            print(f"[PASS] {s}")
    # 전체 실행 시 시나리오 무결성도 함께
    if arg == "all":
        serr = validate_scenario_summary()
        if serr:
            fail += 1
            print("[FAIL] V6 시나리오 요약: " + " / ".join(serr[:10]))
        else:
            print("[PASS] V6 시나리오 요약 무결성")
    print(f"\n{len(sggs)}개 중 실패 {fail}")
    sys.exit(1 if fail else 0)
