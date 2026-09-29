# 맥미니에서 이어서 작업하기

2026-09-29 기준. 윈도우 PC(`C:\Users\user\…`)에서 하던 작업을 맥미니로 옮길 때의 순서입니다.

**가장 먼저 알아 둘 점: 코드 안에 윈도우 경로가 많이 박혀 있습니다.** 모델 저장소 파일 68개와 사이트 저장소 파일 38개에 `C:\Users\user\새 폴더` 같은 경로가 직접 적혀 있어서, 이 경로를 고치기 전에는 대부분의 스크립트가 맥에서 돌지 않습니다(5절).

## 1. 자료 받기 (iCloud)

- iCloud 사본(`Agrivoltaic_2026`)을 맥에서 원하는 위치에 둡니다. 예: `~/Agrivoltaic/`
- **DB 파일(`Ledger_Rebuild/agrivoltaic_ledger_v1.duckdb`, 약 23 GB)은 반드시 "항상 이 기기에 유지"로 설정하세요.** iCloud가 공간 절약으로 파일을 내려 두면 DB를 열 수 없거나 아주 느려집니다.
- 복사가 원본과 같은지 확인할 것:
  - DB 파일 크기 23,169,871,872 bytes
  - `Ledger_Rebuild/retired_1km/` 보관본(`RETIRED_MANIFEST.json` 포함) 존재

## 2. 프로그램 설치

```bash
xcode-select --install
```

```bash
brew install python@3.11 gh git
```

```bash
pip3 install duckdb==1.5.1 geopandas==1.1.3 shapely==2.1.2 pyproj==3.7.2 pandas numpy scipy
```

- 저장소에 requirements 파일이 없어서, 윈도우 PC에서 쓰던 버전을 적었습니다.
- **shapely 2.1 이상**이어야 합니다(자문 경계 파일을 만드는 `coverage_simplify`가 2.1부터 있음).

## 3. 저장소 받기

```bash
gh auth login
```

```bash
cd ~/Agrivoltaic && gh repo clone sojin-droid/agrivoltaic-model model-repo -- -b pr0048-spatial-heterogeneity
```

```bash
cd ~/Agrivoltaic && gh repo clone sojin-droid/Agrivoltaic-Feasibility-V5 site-v5 -- -b v5.5-ggi-review
```

```bash
cd ~/Agrivoltaic && gh repo clone sojin-droid/agrivoltaic-advisory-gg advisory-gg
```

| 저장소 | 이어서 쓸 브랜치 | 옮길 때의 최신 커밋 | 비고 |
|---|---|---|---|
| 모델 (비공개) | `pr0048-spatial-heterogeneity` | `31be3cc` | master는 `f14b620` |
| V5 사이트 | `v5.5-ggi-review` | 이 문서를 넣은 커밋 | production은 `main`(`ffed9b2`, GitHub Pages) — 병합 전까지 건드리지 않기 |
| 자문 화면 | `main` | `ede57ba` | push하면 바로 공개 URL에 배포됨 |

- iCloud 사본 안에도 윈도우에서 쓰던 저장소 폴더가 들어 있을 수 있습니다. **작업은 새로 받은 저장소에서 하세요.** iCloud 폴더 안에서 git 작업을 하면 동기화와 충돌할 수 있습니다.
- DB와 GIS 원자료(`Ledger_Rebuild/`, `GIS_DATA/`)는 git에 없으므로 iCloud 사본을 씁니다.

## 4. 저장소별 설정

**모델 저장소 — 커밋 전 검사 켜기** (clone으로 따라오지 않음)

```bash
cd ~/Agrivoltaic/model-repo && git config core.hooksPath model/hooks
```

- 검사 파일 `model/hooks/pre-commit` 6번째 줄의 `BASE="C:/Users/user/새 폴더"`도 고쳐야 합니다. 고치지 않으면 모든 커밋이 검사에서 막힙니다.
- 검사는 폴더 전체(커밋 안 한 파일 포함)의 용어 규칙을 봅니다. 금지어가 하나라도 남아 있으면 어떤 커밋도 통과하지 못합니다.

**자문 화면 저장소 — 줄바꿈 변환 끄기**

```bash
cd ~/Agrivoltaic/advisory-gg && git config core.autocrlf false
```

- `PACKAGE_MANIFEST.json`이 파일 바이트의 sha256으로 대조하기 때문에, 줄바꿈이 바뀌면 불일치가 납니다.

## 5. 윈도우 경로 고치기 (가장 큰 일)

- 주로 이런 줄들입니다.
  - `ROOT = r"C:\Users\user\새 폴더"` (29곳)
  - `LR = r"C:\Users\user\새 폴더\Ledger_Rebuild"` (24곳)
  - `BASE = r"C:\Users\user\새 폴더\GIS_DATA\…"`
  - 사이트 저장소 `pipeline/` 의 export 스크립트(`LR = …`, `SRC = …`)
- 권장: **환경 변수 하나(예: `AGRI_ROOT`)를 읽도록 한 번에 바꾸기.** 앞으로 PC를 바꿔도 코드를 고칠 필요가 없습니다. 바꾼 뒤 7절의 검사로 확인합니다.
- 폴더 이름 "새 폴더"에 한글과 공백이 있으므로, 맥에서는 영문 이름(예: `~/Agrivoltaic/data`)을 권합니다.

## 6. API 키

- 윈도우 PC에 등록돼 있던 환경 변수: `VWORLD_API_KEY`, `VWORLD_API_KEY_2`~`_6`, `DATA_GO_KR_API_KEY`, `KEPCO_API_KEY`, `LURIS_API_KEY`, `GOOGLE_API_KEY`
- **키 값은 git에도 iCloud 사본에도 없습니다.** 맥에서 `~/.zshrc`에 다시 적어 주세요.

  ```
  export VWORLD_API_KEY="…"
  ```

- 윈도우에서 값 확인: PowerShell `[Environment]::GetEnvironmentVariable("VWORLD_API_KEY","User")`
- 기존 수집 스크립트는 VWorld를 `domain=localhost`로 불러 왔습니다.

## 7. 제대로 되는지 확인

경로를 고친 뒤:

```bash
cd ~/Agrivoltaic/model-repo && python3 model/checks/touchstones.py | tail -3
```

- 기대값: `PASS 210 · FAIL 0 · PENDING 0 · SKIP 0`
- 릴리스 품질 게이트(`model/checks/quality_gate.py`)는 따로 실행합니다. 현재 FAIL 3건(G1·G2·CP13)은 알려진 상태입니다(9절).

```bash
cd ~/Agrivoltaic/site-v5 && python3 pipeline/gate/site_gate.py | tail -1 && python3 pipeline/gate/test_admin_bridge.py | tail -1
```

```bash
cd ~/Agrivoltaic/advisory-gg && python3 -m http.server 8777
```

- 브라우저에서 `http://127.0.0.1:8777/advisory.html`
- 윈도우에서 쓰던 `python -X utf8`은 맥에서는 필요 없습니다(`python3`).

## 8. 자문 화면을 고칠 때의 흐름

- 원본은 `site-v5/advisory.html`(과 `site-v5/data_v4/advisory/`, `docs/ADVISORY_README.md`)입니다.
- 고친 뒤 `advisory-gg/`로 같은 경로에 복사하고, `PACKAGE_MANIFEST.json`의 해당 파일 `bytes`·`sha256`과 `revision`을 갱신해서 push합니다. push하면 GitHub Pages가 1–2분 안에 배포합니다.
- 윈도우의 패키지 폴더(`Agrivoltaic-Advisory-pkg`)는 git에 없는 중간 사본이라 맥에서는 필요 없습니다. 자문 저장소를 기준으로 삼습니다.
- 공개 URL: https://sojin-droid.github.io/agrivoltaic-advisory-gg/advisory.html
- 안내문: https://sojin-droid.github.io/agrivoltaic-advisory-gg/docs/ADVISORY_README.md

## 9. 아직 결정이 남은 것

- 지번 검색 카드의 **"①설치 가능 · …" 표현** — 사업·인허가 가능 여부로 읽힐 수 있음. 그대로 둘지, "분석 조건 통과" 같은 중립 표현으로 바꿀지.
- **릴리스 품질 게이트 FAIL 3건**(G1·G2·CP13) — 팜맵 2019 shp와 규제 합성 레이어의 수집일 원천 증거가 없음(추정해서 채우지 않음).
- **경사 조건 단위(15° / 15%)** 미확정 — 판정은 `slope_final > 15`.
- **기존 시설 × 21m 후보 공간 정본 중첩** 미계산.
- **production main에 ≤1,000m 응축(1km) 계보가 남아 있음** — `v5.5-ggi-review`에서는 폐기 완료. 병합 여부는 따로 결정.
