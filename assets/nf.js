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
    // 커서를 올리면 뜨는 설명 카드 — 같은 곳(경기 화성 후보 공간)의 전후 위성사진
    const TIP = {
      parcel: {title: '지목 기준 — 넓게 잡은 값', img: 'assets/nf_hover_jimok.jpg',
        lines: ['지목상 농지(전·답·과수원) 필지를 모두 셈', '도로·건물·숲이 된 필지도 들어 있음'],
        cap: '노란 선 = 지목상 농지 필지 전부(건물이 들어선 필지 포함)'},
      sat: {title: '위성 기준 — 보수적으로 잡은 값', img: 'assets/nf_hover_sat.jpg',
        lines: ['위성사진 검토로 도로·건물·숲·물가 필지를 뺌', '휴경지 등을 함께 뺐을 수 있음', '검토 범위: 진흥구역 개방 조건 · 법인·국공유 · 1MW 이상 후보 공간'],
        cap: '파란 칠 = 남긴 농지 · 빨간 칠 = 뺀 필지(건물이 들어선 땅)'}
    };
    const pop = document.createElement('div');
    pop.id = 'nf-tip'; pop.setAttribute('role', 'tooltip');
    pop.style.cssText = 'position:fixed;z-index:9999;display:none;width:300px;padding:10px 12px;background:#fff;color:#1d2a22;'
      + 'border:1px solid var(--line,#cfd6cf);border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.18);font-size:12.5px;line-height:1.5;text-align:left';
    document.body.appendChild(pop);
    const show = (k, el) => {
      const t = TIP[k], r = el.getBoundingClientRect();
      pop.innerHTML = `<div style="font-weight:700;margin-bottom:6px">${t.title}</div>`
        + `<img src="${t.img}" alt="" style="display:block;width:100%;border-radius:6px;margin-bottom:6px">`
        + `<div style="color:#5b6b60;font-size:11.5px;margin-bottom:6px">경기 화성 후보 공간 예 · ${t.cap}</div>`
        + t.lines.map(s => `<div>· ${s}</div>`).join('')
        + '<div style="margin-top:6px;color:#5b6b60;font-size:11.5px">실제 설치 가능 면적은 두 값 사이일 가능성이 큼</div>';
      pop.style.display = 'block';
      const left = Math.min(Math.max(8, r.left + r.width / 2 - 150), innerWidth - 308);
      pop.style.left = left + 'px'; pop.style.top = (r.bottom + 8) + 'px';
    };
    const hide = () => { pop.style.display = 'none'; };
    [['parcel', false, '지목'], ['sat', true, '위성']].forEach(([k, val, label]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.setAttribute('aria-pressed', on === val ? 'true' : 'false'); b.setAttribute('aria-describedby', 'nf-tip');
      b.addEventListener('mouseenter', () => show(k, b)); b.addEventListener('focus', () => show(k, b));
      b.addEventListener('mouseleave', hide); b.addEventListener('blur', hide);
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
