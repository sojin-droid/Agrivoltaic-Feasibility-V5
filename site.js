/* PLANiT Shipping — 공통 인터랙션 (수정할 필요 없음) */
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* 항로 실선 채움 트리거 */
window.addEventListener('load', () => document.body.classList.add('loaded'));

/* 스크롤 리빌 */
const io = new IntersectionObserver(es => {
  es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
}, { threshold: .12 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));
/* 데이터 로드 후 주입되는 .reveal(예: index의 다섯 단계 박스)도 감지해 등록 */
new MutationObserver(() => {
  document.querySelectorAll('.reveal:not(.in)').forEach(el => io.observe(el));
}).observe(document.body, { childList: true, subtree: true });

/* 진행 바 (.pbar .fill, .series-progress .fill) */
document.querySelectorAll('.pbar .fill, .series-progress .fill').forEach(fill => {
  const pio = new IntersectionObserver(es => {
    es.forEach(e => {
      if (e.isIntersecting) { fill.style.width = (fill.dataset.progress || 0) + '%'; pio.unobserve(fill); }
    });
  }, { threshold: .5 });
  pio.observe(fill);
});

/* 숫자 카운트업 (.count[data-target]) */
document.querySelectorAll('.count').forEach(el => {
  const cio = new IntersectionObserver(es => {
    es.forEach(e => {
      if (!e.isIntersecting) return;
      cio.unobserve(el);
      const target = +el.dataset.target;
      if (reduced) { el.textContent = target.toLocaleString(); return; }
      const dur = 1400, t0 = performance.now();
      (function tick(t) {
        const p = Math.min((t - t0) / dur, 1);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
        if (p < 1) requestAnimationFrame(tick);
      })(t0);
    });
  }, { threshold: .6 });
  cio.observe(el);
});

/* 모바일 메뉴: 링크 클릭 시 닫기 */
document.querySelectorAll('#menu a').forEach(a =>
  a.addEventListener('click', () => document.getElementById('menu').classList.remove('open')));

/* ─────────────────────────────────────────────────────────────
   i18n (KO/EN) — 공용 엔진
   · 페이지가 site.js 로드 '이전'에 window.I18N = { en:{키:값,…}, meta:{ en:{title,desc} } } 를
     정의하면 활성화. 사전이 없는 페이지는 자동 no-op.
   · data-i18n="키" 요소만 스왑. ko = DOM 원본 캡처, en = I18N.en[키].
   · 현재 언어에 값이 없으면 display:none (ko-only / en-only 양방향 숨김).
   · 상태: ?lang=en (source of truth) → localStorage('planit_lang') → 기본 ko.
   · <html lang> · <title> · meta[description] · 토글 버튼 상태 · #appendix 동시 갱신.
   · 동적 콘텐츠(map 등)는 window.__curLang 를 읽고 window.onLangChange(lang) 훅으로 재렌더.
   ───────────────────────────────────────────────────────────── */
(function () {
  var I18N = window.I18N;
  if (!I18N || !I18N.en) { window.__curLang = 'ko'; return; }
  var EN = I18N.en, META = (I18N.meta && I18N.meta.en) || null;
  var nodes = [].slice.call(document.querySelectorAll('[data-i18n]'));
  var orig = new Map();
  nodes.forEach(function (el) { orig.set(el, (el instanceof SVGElement) ? el.textContent : el.innerHTML); });
  var oTitle = document.title;
  var md = document.querySelector('meta[name="description"]');
  var oDesc = md ? md.getAttribute('content') : '';
  var btns = [].slice.call(document.querySelectorAll('.lang-toggle [data-lang]'));

  function setEl(el, val) {
    var has = val != null && String(val).trim() !== '';
    el.style.display = has ? '' : 'none';
    if (!has) return;
    if (el instanceof SVGElement) el.textContent = val; else el.innerHTML = val;
  }
  function apply(lang) {
    nodes.forEach(function (el) { setEl(el, lang === 'en' ? EN[el.getAttribute('data-i18n')] : orig.get(el)); });
    document.documentElement.lang = lang;
    if (META) {
      document.title = lang === 'en' ? META.title : oTitle;
      if (md) md.setAttribute('content', lang === 'en' ? META.desc : oDesc);
    }
    var apx = document.getElementById('appendix');           // KO 전용 용어집·FAQ
    if (apx) apx.style.display = lang === 'en' ? 'none' : '';
    btns.forEach(function (b) {
      var on = b.getAttribute('data-lang') === lang;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    try { localStorage.setItem('planit_lang', lang); } catch (e) {}
    try {
      var u = new URL(location.href);
      if (lang === 'en') u.searchParams.set('lang', 'en'); else u.searchParams.delete('lang');
      history.replaceState(null, '', u);                     // file:// (origin null)에서는 예외 → 무시
    } catch (e) {}
    window.__curLang = lang;
    if (typeof window.onLangChange === 'function') { try { window.onLangChange(lang); } catch (e) {} }
  }
  function initial() {
    var p = new URLSearchParams(location.search).get('lang');
    if (p === 'en' || p === 'ko') return p;
    try { var s = localStorage.getItem('planit_lang'); if (s === 'en' || s === 'ko') return s; } catch (e) {}
    return 'ko';
  }
  btns.forEach(function (b) { b.addEventListener('click', function () { apply(b.getAttribute('data-lang')); }); });
  window.__setLang = apply;
  apply(initial());
})();
