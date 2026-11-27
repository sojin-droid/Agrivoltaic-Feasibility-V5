/* 비농지 제외 사례 켜기·끄기 — 기본은 끔(지목 기준).
   끔: data_v4_base/manifest.json 에 있는 파일은 data_v4_base/ 에서 읽는다(2026-10-14 발행본 — 비농지 제외·띠 필지 제외 전, 법인·국공유 조건).
   켬: data_v4/ 그대로(비농지 제외 사례 반영 — 자동 제외 · 위성사진 육안 검토 · 사용자 정정).
   개인 포함(@all) 조건의 지도 도형은 한 벌뿐이라 끄고 켜도 같다(비농지 제외 반영본).
   비농지 검토·자문 화면은 검토 결과를 보여 주는 화면이라 늘 켬으로 읽는다.
   상태는 이 브라우저에만 저장(localStorage) · 주소에 ?nf=1 / ?nf=0 을 붙이면 그 상태로 연다. */
(function () {
  const KEY = 'v5_nonfarm', ALWAYS_ON = ['advisory.html', 'cluster_advisory.html', 'nonfarm.html', 'nonfarm_cases.html'];
  const page = (location.pathname.split('/').pop() || 'index.html');
  let on = false;
  try {
    const q = new URLSearchParams(location.search).get('nf');
    if (q === '1' || q === '0') localStorage.setItem(KEY, q);
    on = localStorage.getItem(KEY) === '1';
  } catch (e) { /* 저장소를 못 쓰면 기본(끔) */ }
  const fixed = ALWAYS_ON.includes(page);
  if (fixed) on = true;
  window.V5NF = { on, fixed, pick: (onText, offText) => (on ? onText : offText) };
  document.documentElement.classList.add(on ? 'nf-on' : 'nf-off');
  const css = document.createElement('style');
  css.textContent = 'html.nf-on .nf-off-only,html.nf-off .nf-on-only{display:none}';
  document.head.appendChild(css);

  if (!on) {
    const _fetch = window.fetch.bind(window);
    const man = _fetch('data_v4_base/manifest.json').then(r => (r.ok ? r.json() : { files: [] })).then(m => new Set(m.files)).catch(() => new Set());
    window.fetch = async function (input, init) {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const m = url.match(/^(?:\.\/)?data_v4\/([^?#]+)(.*)$/);
      if (m && (await man).has(m[1])) return _fetch('data_v4_base/' + m[1] + m[2], init);
      return _fetch(input, init);
    };
  }

  function chip() {
    if (fixed || document.getElementById('nf-chip')) return;
    const host = document.querySelector('header.nav .menu') || document.querySelector('header.nav') || document.querySelector('nav');
    if (!host) return;
    // 두 칸 단추: 필지 모양 = 지목 기준 · 위성 모양 = 위성사진으로 비농지를 거른 값
    const ICON = {
      parcel: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M3 5l8-2 2 7-9 3z"/><path d="M11 3l9 3-2 7-5-3"/><path d="M4 13l9-3 5 3-3 8-9-2z"/></svg>',
      sat: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="6" height="6" rx="1" transform="rotate(45 12 12)"/><path d="M8.5 8.5l-4-4M6.2 2.8L2.8 6.2"/><path d="M15.5 15.5l4 4M17.8 21.2l3.4-3.4"/><path d="M16 4.5a4 4 0 0 1 3.5 3.5M16 1.5a7 7 0 0 1 6.5 6.5"/></svg>'
    };
    const box = document.createElement('span');
    box.id = 'nf-chip'; box.setAttribute('role', 'group'); box.setAttribute('aria-label', '값 기준');
    box.style.cssText = 'display:inline-flex;margin-left:10px;border:1px solid var(--line,#cfd6cf);border-radius:16px;overflow:hidden;vertical-align:middle;white-space:nowrap';
    [['parcel', false, '지목', '지목 기준 값 — 지목상 농지 필지로 계산'], ['sat', true, '위성', '위성사진으로 비농지 필지를 거른 값(비농지 제외 사례)']].forEach(([k, val, label, tip]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.title = tip; b.setAttribute('aria-pressed', on === val ? 'true' : 'false');
      b.innerHTML = ICON[k] + '<span style="margin-left:4px">' + label + '</span>';
      b.style.cssText = 'display:inline-flex;align-items:center;padding:4px 10px;border:0;font:inherit;font-size:12px;cursor:pointer;'
        + (on === val ? 'background:var(--leaf-deep,#2f6b3a);color:#fff' : 'background:transparent;color:inherit');
      b.addEventListener('click', () => {
        if (on === val) return;
        try { localStorage.setItem(KEY, val ? '1' : '0'); } catch (e) { /* 무시 */ }
        const u = new URL(location.href); u.searchParams.delete('nf'); location.href = u.toString();
      });
      box.appendChild(b);
    });
    host.appendChild(box);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', chip); else chip();
})();
