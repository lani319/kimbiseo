// ==UserScript==
// @name         TTM 자동 새로고침 & BUY NOW 클릭 (XPath 지정)
// @namespace    local.ttm.autobuy
// @version      1.2
// @description  지정 시각부터 로딩 완료 후 1초 간격 새로고침, XPath 요소가 BUY NOW면 클릭
// @match        https://www.thaiticketmajor.com/*
// @match        https://thaiticketmajor.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  // ============ 여기만 수정 ============
  const XPATH = '//*[@id="section-event"]/div/div[2]/div/div/div[1]/div[1]/div/div[12]/div/div[2]/a/small';
  const START_TIME = '2026-10-16T11:45:00';  // 한국 시간 오늘 11:45 정각
  const RELOAD_DELAY = 1000;                 // 로딩 완료 후 대기 (ms)
  const WAIT_TIMEOUT = 15000;                // 로딩 지연 시 강제 새로고침 기준 (ms)
  // =====================================

  const startTime = new Date(START_TIME).getTime();
  if (isNaN(startTime)) { console.error('[TTM] START_TIME 형식 오류'); return; }

  const doneKey = 'ttm_done_' + Date.now(); // 세션당 1회 클릭
  let found = false;

  // ---------- HUD ----------
  const hud = document.createElement('div');
  hud.style.cssText = 'position:fixed;top:0;right:0;z-index:2147483647;background:rgba(0,0,0,.8);color:#0f0;'
    + 'padding:6px 10px;font:12px/1.5 monospace;border-radius:0 0 0 6px;white-space:pre;pointer-events:none;';
  (document.documentElement || document).appendChild(hud);
  const setHud = (t) => { hud.textContent = t; };
  const log = (...a) => console.log('[TTM]', ...a);

  function fmt(ms) {
    if (ms <= 0) return '00:00:00';
    const s = Math.floor(ms / 1000);
    return String(Math.floor(s / 3600)).padStart(2, '0') + ':'
      + String(Math.floor(s % 3600 / 60)).padStart(2, '0') + ':'
      + String(s % 60).padStart(2, '0');
  }

  // ---------- XPath 타겟 확인 ----------
  function getTarget() {
    const r = document.evaluate(XPATH, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    const node = r.singleNodeValue;
    if (!node) return null;
    const text = (node.textContent || '').trim();
    const anchor = node.closest('a') || node;
    return { text, anchor };
  }

  // ---------- 메인 ----------
  const loadStart = Date.now();
  let attempts = 0;

  function tick() {
    if (found) { setHud('✔ BUY NOW 클릭 완료\n새로고침 중지됨'); return; }

    const now = Date.now();

    // 시작 전: 카운트다운만
    if (now < startTime) {
      setHud('대기 중… 시작까지 ' + fmt(startTime - now));
      setTimeout(tick, 500);
      return;
    }

    // DOM 로딩 완료 확인 — 안 끝났으면 절대 새로고침 안 함
    const domReady = document.readyState === 'complete'
      && document.querySelector('div.event-item') !== null;

    if (!domReady) {
      const waited = now - loadStart;
      setHud('로딩 중… ' + Math.round(waited / 1000) + 's (새로고침 보류)');
      if (waited > WAIT_TIMEOUT) {
        log('로딩 ' + Math.round(waited / 1000) + 's 초과 → 강제 새로고침');
        location.reload();
        return;
      }
      setTimeout(tick, 250);
      return;
    }

    const t = getTarget();

    // BUY NOW → 클릭 후 중지
    if (t && /buy now/i.test(t.text)) {
      found = true;
      setHud('★ BUY NOW 감지! 클릭함');
      log('클릭 →', t.anchor.href);
      t.anchor.click();
      return;
    }

    // Coming Soon이거나 요소 없음 → 1초 후 새로고침
    attempts++;
    const status = t ? ('"' + t.text + '"') : '요소 없음 (레이아웃 변화 의심)';
    setHud('현재: ' + status + '\n' + attempts + '회차 — 1초 후 새로고침');
    setTimeout(() => location.reload(), RELOAD_DELAY);
  }

  tick();
})();
