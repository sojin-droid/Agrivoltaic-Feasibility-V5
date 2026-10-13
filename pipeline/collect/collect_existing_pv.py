# /// script
# requires-python = ">=3.9"
# dependencies = ["requests"]
# ///
# -*- coding: utf-8 -*-
"""기존 태양광 원천 수집 — 공공데이터포털 「전국태양광발전소전기사업허가정보표준데이터」(15107742) 전국 전량.

원천을 손대지 않고 페이지 그대로 저장한다(가공은 export_existing_pv.py). 같은 날 다시 돌리면 받은 페이지는 건너뛴다.
  저장: $AGRI_ROOT/raw/existing_pv/std_15107742/<YYYYMMDD>/page_0001.json … + manifest.json(건수·받은 시각·요청 조건)
  키:   DATA_GO_KR_API_KEY (공공데이터포털 → 해당 데이터 '활용신청' → 마이페이지의 일반 인증키(Decoding)) — README '외부 API 키'
사용: uv run pipeline/collect/collect_existing_pv.py            (AGRI_ROOT 없으면 ~/Developer/agri-data)
"""
import datetime, json, os, sys, time
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
EP = 'https://api.data.go.kr/openapi/tn_pubr_public_solar_gen_flct_api'
ROWS = 1000                     # 원천 상한
KEY = os.environ.get('DATA_GO_KR_API_KEY')
if not KEY:
    sys.exit("DATA_GO_KR_API_KEY 환경 변수가 없습니다 — 공공데이터포털에서 15107742 활용신청 후 일반 인증키(Decoding)를 설정하세요 (README '외부 API 키')")
ROOT = os.environ.get('AGRI_ROOT') or os.path.expanduser('~/Developer/agri-data')
DAY = datetime.date.today().strftime('%Y%m%d')
OUT = os.path.join(ROOT, 'raw', 'existing_pv', 'std_15107742', DAY)
os.makedirs(OUT, exist_ok=True)
S = requests.Session()


def page(no):
    """한 페이지 — 실패는 3번까지 다시. 원천 오류 코드는 그대로 드러낸다."""
    for k in range(3):
        try:
            r = S.get(EP, params={'serviceKey': KEY, 'pageNo': no, 'numOfRows': ROWS, 'type': 'json'}, timeout=60)
            if r.status_code == 200 and r.text.lstrip().startswith('{'):
                d = r.json()
                head = d.get('response', {}).get('header', {})
                if head.get('resultCode') in ('00', '0', None):
                    return d
                if head.get('resultCode') == '03':          # NODATA — 마지막 다음 페이지
                    return d
                raise RuntimeError(f"원천 오류 {head.get('resultCode')} {head.get('resultMsg')}")
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            if k == 2:
                raise
            print(f"  page {no} 재시도 ({e})", flush=True)
            time.sleep(3 * (k + 1))


def body(d):
    b = d.get('response', {}).get('body', {}) or {}
    items = b.get('items') or []
    if isinstance(items, dict):                 # 응답 형식 차이(items.item) 흡수
        items = items.get('item') or []
    if isinstance(items, dict):
        items = [items]
    return int(b.get('totalCount') or 0), items


first = page(1)
total, items = body(first)
pages = max(1, -(-total // ROWS))
print(f"원천 전체 {total:,}건 · {pages}페이지 → {OUT}", flush=True)
json.dump(first, open(os.path.join(OUT, 'page_0001.json'), 'w', encoding='utf-8'), ensure_ascii=False)
got = len(items)
for no in range(2, pages + 1):
    fp = os.path.join(OUT, f'page_{no:04d}.json')
    if os.path.exists(fp):
        got += len(body(json.load(open(fp, encoding='utf-8')))[1])
        continue
    d = page(no)
    json.dump(d, open(fp, 'w', encoding='utf-8'), ensure_ascii=False)
    got += len(body(d)[1])
    if no % 20 == 0 or no == pages:
        print(f"  [{no}/{pages}] 누계 {got:,}", flush=True)
    time.sleep(0.2)

json.dump({'dataset': 'data.go.kr 15107742 전국태양광발전소전기사업허가정보표준데이터', 'endpoint': EP,
           'retrieved_at': datetime.datetime.now().isoformat(timespec='seconds'), 'total_count': total,
           'rows_saved': got, 'pages': pages, 'rows_per_page': ROWS},
          open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"완료 — {got:,}/{total:,}건 저장")
if got != total:
    sys.exit(f"건수 불일치 {got} ≠ {total} — 같은 날 다시 돌리면 빠진 페이지만 받는다")
