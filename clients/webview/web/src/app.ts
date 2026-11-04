import { MarketApi, MarketController, stockCurrency, type Category, type Country, type MarketState } from './market.js';

const root = document.querySelector<HTMLElement>('#app');
if (!root) throw new Error('앱 화면을 찾을 수 없습니다.');
// This template contains fixed product copy only. All remote/user strings use textContent.
root.innerHTML = `
  <header class="service-header"><a class="brand" href="/" aria-label="DAYNOMY 홈">DAYNOMY<span class="brand-dot" aria-hidden="true"></span></a><span class="header-context">종목 조회</span></header>
  <main id="main" class="workspace">
    <div class="page-heading"><h1>종목과 거래 단가</h1><p>종목을 고르면 최근 종가를 불러와요.<br class="mobile-break"> 단가는 언제든 직접 입력할 수 있어요.</p></div>
    <div class="editor-grid">
      <section class="search-section" aria-labelledby="search-heading">
        <h2 id="search-heading">종목 찾기</h2>
        <fieldset class="country-field"><legend>국가</legend><div class="segmented" id="countries"><button type="button" data-country="KR" aria-pressed="true">한국</button><button type="button" data-country="US" aria-pressed="false">미국</button></div></fieldset>
        <div class="field"><label for="stock-query">종목 검색</label><input id="stock-query" type="search" autocomplete="off" spellcheck="false" placeholder="종목명 또는 종목 코드" aria-describedby="search-help search-status"><p id="search-help" class="field-help">검색 결과는 최대 20개예요. 유형을 선택해 좁혀 보세요.</p></div>
        <div class="filters" role="group" aria-label="종목 유형"><button type="button" data-category="ALL" aria-pressed="true">전체</button><button type="button" data-category="STOCK" aria-pressed="false">주식</button><button type="button" data-category="ETF" aria-pressed="false">ETF</button></div>
        <div class="results-heading"><h3>검색 결과</h3><span id="result-count" class="muted"></span></div>
        <p id="search-status" class="status-message" role="status" aria-live="polite"></p>
        <button id="retry-search" class="secondary-button" type="button" hidden>검색 다시 시도</button>
        <ul id="results" class="results" aria-label="종목 검색 결과"></ul>
      </section>
      <section class="price-section" aria-labelledby="price-heading">
        <h2 id="price-heading">거래 단가</h2>
        <div id="selection-empty" class="selection-empty"><p class="empty-title">조회할 종목을 선택해 주세요</p><p>검색창에서 종목을 찾아보세요.<br>선택한 종목의 최근 저장 종가를 확인할 수 있어요.</p></div>
        <div id="selection" hidden><div class="selected-stock"><div><h3 id="selected-name"></h3><p id="selected-meta" class="muted"></p></div><button type="button" id="clear-selection" class="text-button">선택 해제</button></div>
          <div class="field price-field"><label for="unit-price">거래 단가 <span id="currency" class="currency"></span></label><input id="unit-price" type="text" inputmode="decimal" autocomplete="off" placeholder="단가를 입력해 주세요" aria-describedby="price-status price-help"><p id="price-status" class="status-message" role="status" aria-live="polite"></p><button id="retry-price" class="secondary-button" type="button" hidden>최근 종가 다시 조회</button><p id="price-help" class="field-help">직접 입력한 단가는 조회 결과가 바뀌어도 유지돼요.</p></div>
          <div class="quote-note"><span id="price-source">최근 저장 종가</span><span id="base-date"></span></div>
        </div>
        <p class="scope-note">현재는 조회와 단가 입력만 가능해요.<br>로그인과 거래 저장은 지원하지 않습니다.</p>
      </section>
    </div>
  </main>
  <footer class="service-footer">DAYNOMY <span>나의 자산을 기록하는 첫 단계</span></footer>`;

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id); if (!found) throw new Error(`화면 요소 누락: ${id}`); return found as T;
}
const query = element<HTMLInputElement>('stock-query');
const unitPrice = element<HTMLInputElement>('unit-price');
const results = element<HTMLUListElement>('results');
const searchStatus = element('search-status');
const priceStatus = element('price-status');
const retrySearch = element<HTMLButtonElement>('retry-search');
const retryPrice = element<HTMLButtonElement>('retry-price');
const countryButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-country]'));
const categoryButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-category]'));
const controller = new MarketController(new MarketApi(), render);

function render(state: MarketState): void {
  if (query.value !== state.query) query.value = state.query;
  if (unitPrice.value !== state.unitPrice) unitPrice.value = state.unitPrice;
  query.disabled = Boolean(state.selected);
  countryButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.country === state.country)));
  categoryButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.category === state.category)));
  const visible = controller.visibleStocks;
  results.replaceChildren();
  for (const stock of visible) {
    const li = document.createElement('li');
    const button = document.createElement('button'); button.type = 'button'; button.className = 'stock-result';
    const name = document.createElement('span'); name.className = 'stock-name'; name.textContent = stock.name;
    const details = document.createElement('span'); details.className = 'stock-meta'; details.textContent = `${stock.assetCode} · ${String(stock.market)} · ${stock.category === 'ETF' ? 'ETF' : '주식'}`;
    button.append(name, details); button.addEventListener('click', () => { controller.select(stock); unitPrice.focus(); }); li.append(button); results.append(li);
  }
  element('result-count').textContent = state.searchStatus === 'ready' ? `${visible.length}개` : '';
  const message = state.selected ? '선택한 종목의 단가를 확인해 주세요.'
    : state.searchStatus === 'loading' ? '종목을 검색하고 있어요.'
    : state.searchStatus === 'error' ? state.searchError ?? ''
    : state.searchStatus === 'ready' ? visible.length ? '' : state.stocks.length ? '선택한 유형의 종목이 없어요. 다른 유형을 선택해 보세요.' : '검색 결과가 없어요. 종목명이나 코드를 확인해 주세요.'
    : '종목명 또는 코드를 입력해 주세요.';
  searchStatus.textContent = message;
  searchStatus.classList.toggle('error', state.searchStatus === 'error');
  results.setAttribute('aria-busy', String(state.searchStatus === 'loading'));
  retrySearch.hidden = state.searchStatus !== 'error';
  element('selection-empty').hidden = Boolean(state.selected);
  element('selection').hidden = !state.selected;
  if (state.selected) {
    element('selected-name').textContent = state.selected.name;
    element('selected-meta').textContent = `${state.selected.assetCode} · ${String(state.selected.market)}`;
    const currency = stockCurrency(state.selected);
    element('currency').textContent = currency === 'KRW' ? '(KRW)' : currency === 'USD' ? '(USD)' : '';
  }
  priceStatus.textContent = state.priceStatus === 'loading' ? '최근 종가를 불러오고 있어요. 직접 입력해도 괜찮아요.'
    : state.priceStatus === 'error' ? state.priceError ?? ''
    : state.dirty ? '직접 입력한 단가예요.' : state.priceStatus === 'ready' ? '최근 종가를 단가에 입력했어요.' : '';
  priceStatus.classList.toggle('error', state.priceStatus === 'error');
  unitPrice.setAttribute('aria-busy', String(state.priceStatus === 'loading'));
  retryPrice.hidden = state.priceStatus !== 'error';
  element('base-date').textContent = state.baseDate ?? '조회 전';
  element('price-source').textContent = state.baseDate ? '종가 기준일' : '최근 저장 종가';
}
query.addEventListener('input', () => controller.setQuery(query.value));
unitPrice.addEventListener('input', () => controller.setUnitPrice(unitPrice.value));
countryButtons.forEach(button => button.addEventListener('click', () => controller.setCountry(button.dataset.country as Country)));
categoryButtons.forEach(button => button.addEventListener('click', () => controller.setCategory(button.dataset.category as Category)));
element('clear-selection').addEventListener('click', () => { controller.clearSelection(); query.focus(); });
retrySearch.addEventListener('click', () => controller.retrySearch());
retryPrice.addEventListener('click', () => controller.retryPrice());

let pageActive = true;
let nativeActive = true;
const syncActivity = () => controller.setActive(pageActive && nativeActive && document.visibilityState !== 'hidden');
window.addEventListener('pagehide', () => { pageActive = false; syncActivity(); });
window.addEventListener('pageshow', () => { pageActive = true; syncActivity(); });
document.addEventListener('visibilitychange', syncActivity);
window.addEventListener('daynomy:active', event => {
  if (!(event instanceof CustomEvent) || typeof event.detail !== 'boolean') return;
  nativeActive = event.detail; syncActivity();
});
render(controller.state);
syncActivity();
