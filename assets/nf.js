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
    const b = document.createElement('button');
    b.id = 'nf-chip'; b.type = 'button';
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.title = on ? '지금: 비농지 제외 사례 반영 값 — 누르면 지목 기준 값으로' : '지금: 지목 기준 값 — 누르면 비농지 제외 사례 반영 값으로';
    b.textContent = '비농지 제외 ' + (on ? '켬' : '끔');
    b.style.cssText = 'margin-left:10px;padding:4px 10px;border-radius:14px;font:inherit;font-size:12px;cursor:pointer;white-space:nowrap;'
      + (on ? 'background:var(--leaf-deep,#2f6b3a);color:#fff;border:1px solid var(--leaf-deep,#2f6b3a)' : 'background:transparent;color:inherit;border:1px solid currentColor');
    b.addEventListener('click', () => {
      try { localStorage.setItem(KEY, on ? '0' : '1'); } catch (e) { /* 무시 */ }
      const u = new URL(location.href); u.searchParams.delete('nf'); location.href = u.toString();
    });
    host.appendChild(b);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', chip); else chip();
})();
