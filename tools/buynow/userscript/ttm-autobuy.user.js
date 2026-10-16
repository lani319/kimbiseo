// ==UserScript==
// @name         TTM 자동 새로고침 & BUY NOW 클릭 (XPath 지정)
// @namespace    local.ttm.autobuy
// @version      1.3
// @description  지정 시각부터 로딩 완료 후 1초 간격 새로고침(최대 N회), XPath 요소가 BUY NOW면 클릭 후 완전 중지
// @match        https://www.thaiticketmajor.com/*
// @match        https://thaiticketmajor.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  // ============ 여기만 수정 ============
  const XPATH = '//*[@id="section-event"]/div/div[2]/div/div/div[1]/div[1]/div/div[12]/div/div[2]/a/small';
  const START_TIME = '2026-10-16T11:45:00+09:00'; // +09:00 = 한국시간 (PC 시간대와 무관)
  const MAX_RELOADS = 10;                         // 새로고침 최대 횟수 (넘으면 중지)
  const RELOAD_DELAY = 1000;                      // 로딩 완료 후 대기 (ms)
  const WAIT_TIMEOUT = 15000;                     // 로딩 자체가 안 끝날 때 강제 새로고침 기준 (ms)
  const LIST_WAIT = 8000;                         // 로딩 완료 후 공연 목록이 안 보이면 '대상 페이지 아님'으로 중지 (ms)
  // =====================================

  const startTime = new Date(START_TIME).getTime();
  if (isNaN(startTime)) { console.error('[TTM] START_TIME 형식 오류'); return; }

  // 탭(sessionStorage) 단위 상태. 새로고침해도 유지되고, 탭을 닫으면 초기화.
  // START_TIME 을 바꾸면 키가 달라져 새로 시작.
  const KEY = 'ttm_' + START_TIME;
  const store = {
    get(k) { try { return sessionStorage.getItem(KEY + k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(KEY + k, v); } catch (e) { /* ignore */ } },
  };

  // [수정 1] 이미 클릭했거나 중지된 탭이면 아무것도 하지 않음 → 좌석/결제 페이지에서 새로고침 안 함
  const stopped = store.get('_stop');
  if (stopped) { console.log('[TTM] 중지 상태(' + stopped + ') — 이 탭에서는 동작 안 함'); return; }

  // ---------- HUD ----------
  const hud = document.createElement('div');
  hud.id = 'ttm-hud';
  hud.style.cssText = 'position:fixed;top:0;right:0;z-index:2147483647;background:rgba(0,0,0,.8);color:#0f0;'
    + 'padding:6px 10px;font:12px/1.5 monospace;border-radius:0 0 0 6px;white-space:pre;pointer-events:none;';
  // document-start 에서는 <html> 이 아직 없을 수 있음. 그때 document 에 붙이면
  // HUD 가 문서 루트가 되어 페이지가 아예 안 그려지므로, <html> 이 생긴 뒤에 붙인다.
  const setHud = (t) => {
    hud.textContent = t;
    if (!hud.isConnected && document.documentElement) document.documentElement.appendChild(hud);
  };
  const log = (...a) => console.log('[TTM]', ...a);

  function stop(reason, msg) {
    store.set('_stop', reason);
    setHud(msg + '\n(다시 하려면 탭을 닫고 새로 열기)');
    log('중지:', reason);
  }

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

  // [수정 2] 새로고침 횟수는 sessionStorage 에 누적 → 새로고침해도 초기화되지 않음
  function reloadOrStop(status) {
    const n = Number(store.get('_count') || 0) + 1;
    if (n > MAX_RELOADS) {
      stop('max', '■ ' + MAX_RELOADS + '회 새로고침 후에도 BUY NOW 없음 → 중지\n마지막: ' + status);
      return;
    }
    store.set('_count', String(n));
    setHud('현재: ' + status + '\n' + n + '/' + MAX_RELOADS + '회차 — 1초 후 새로고침');
    setTimeout(() => location.reload(), RELOAD_DELAY);
  }

  // ---------- 메인 ----------
  const loadStart = Date.now();
  let completeAt = 0;

  function tick() {
    const now = Date.now();

    // 시작 전: 카운트다운만
    if (now < startTime) {
      setHud('대기 중… 시작까지 ' + fmt(startTime - now) + '\n최대 ' + MAX_RELOADS + '회 새로고침');
      setTimeout(tick, 500);
      return;
    }

    // 로딩 자체가 안 끝남 → 오래 걸리면 강제 새로고침 (이것도 횟수에 포함)
    if (document.readyState !== 'complete') {
      const waited = now - loadStart;
      setHud('로딩 중… ' + Math.round(waited / 1000) + 's (새로고침 보류)');
      if (waited > WAIT_TIMEOUT) { reloadOrStop('로딩 ' + Math.round(waited / 1000) + 's 초과'); return; }
      setTimeout(tick, 250);
      return;
    }

    // 차단 페이지면 즉시 중지 (계속 새로고침하면 차단이 길어짐)
    const bodyText = document.body ? document.body.innerText : '';
    if (/access denied|you don't have permission/i.test(bodyText)) {
      stop('denied', '■ Access Denied — 자동 중지\n1~2분 뒤 직접 접속하세요');
      return;
    }

    // [수정 1] 로딩은 끝났는데 공연 목록이 없음 → 목록 페이지가 아님(좌석/결제 등) → 새로고침 없이 종료
    if (document.querySelector('div.event-item') === null) {
      if (!completeAt) completeAt = now;
      if (now - completeAt > LIST_WAIT) {
        hud.remove();
        log('공연 목록 없음 → 대상 페이지 아님, 동작 안 함');
        return;
      }
      setHud('공연 목록 표시 대기…');
      setTimeout(tick, 250);
      return;
    }

    const t = getTarget();

    // BUY NOW → 중지 플래그를 먼저 남기고 클릭 (다음 페이지에서 스크립트가 다시 돌지 않도록)
    if (t && /buy now/i.test(t.text)) {
      stop('clicked', '★ BUY NOW 클릭 완료 — 자동 동작 중지\n좌석 선택·결제는 직접 하세요');
      log('클릭 →', t.anchor.href);
      t.anchor.click();
      return;
    }

    // Coming Soon이거나 요소 없음 → 1초 후 새로고침 (최대 횟수까지)
    reloadOrStop(t ? ('"' + t.text + '"') : '요소 없음 (레이아웃 변화 의심)');
  }

  tick();
})();
