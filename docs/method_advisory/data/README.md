# 그림 데이터 (자문용 기술 통계)

정본 산출을 읽어 만든 분포 요약이다. 정본 수치가 아니며 인용은 `model/query.py` 산출로 한다.

| 파일 | 내용 | 원천 |
|---|---|---|
| f01_* | k-거리 곡선 무릎·분위 | step4_1_gaps_S1.parquet · step4_1_kneedle_S1.csv |
| f02_* | 4-최근접 간격 누적 비율 | step4_1_gaps_S1.parquet |
| f03_* | 21m 단위 면적·필지 수(전량, 하한 없음) | scenario_runs/R2_promo/clusters.parquet |
| f04_*·f05_* | 3축 분위·순위상관(3MW 이상) | scenario_runs/R2_promo/block_context.parquet |
| f06_* | 반경 안 산업단지 수(탐색) | block_context x,y × data_v4/ind_bnd.json.gz |
| f07_* | 읍면동 계통 참고값 | DuckDB grid_emd_v3 |
| f08_* | 시군 모집단 대 비지배 비율 | data_v4/top10/*.json.gz R2_promo |

점검 로그: ('d4 n', 7106500) · ('block_context n', 388496, 'min area', 0.0) · ('ind nearest recompute median abs diff km', 0.003)
