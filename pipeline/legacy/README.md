# legacy — 구세대 스크립트 (돌리지 않는다)

여기 있는 36개는 **옛 원장 구축(01~21g)과 site_v2 발행**에 쓰던 것들이다.
`data_v4` 를 만들지 않으므로 현행 발행 경로에 없다. 지우지 않고 두는 이유는
그때의 판단 근거(수집 방법·정정 이력)가 코드에만 남아 있는 것이 있어서다.

되살릴 일이 생기면 그대로 돌리지 말 것 — 경로가 `pipeline/paths.py` 로
옮겨졌고, 여기 파일들은 아직 옛 방식으로 경로를 계산한다.

현행 발행은 저장소 뿌리의 `publish.py` 한 줄이다.

## ≤1,000m 응축(cc) 계보 — 완전 폐기 (2026-09-27)

`export_cand_v4.py` · `export_emd_v4.py` · `make_sgg_briefs.py` 와 발행 자산 `data_v4/cand/` · `recommend_cc_v4` · `recommend_emd_v4` ·
`cand_index` · `emd_index` · `assets/cand.js/css` 는 V5.5 작업 트리에서 제거했다(사용자 지시: active lineage 에서 완전 폐기).
과거 파일은 git 이력(`main` 포함)에만 있다 — V5 production(`main`)은 수정하지 않았다. 과거 cc 산출 원본은 PAPER-FREEZE-001 에 있다.
