export type Country = 'KR' | 'US';
export type Category = 'ALL' | 'STOCK' | 'ETF';
export type Stock = { assetId: number; assetCode: string; name: string; category: 'STOCK' | 'ETF'; market: string; currency?: unknown };
export type StockPrice = { assetId: number; assetCode: string; name: string; baseDate: string; closePrice: number; currency?: unknown };

const markets = ['KOSPI', 'KOSDAQ', 'NASDAQ', 'NYSE', 'NYSE_ARCA', 'NYSE_AMERICAN', 'BATS'];
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null; }
function identity(value: Record<string, unknown>): boolean {
  return Number.isSafeInteger(value.assetId) && Number(value.assetId) > 0 && typeof value.assetCode === 'string' && typeof value.name === 'string';
}
export function decodeStocks(value: unknown): Stock[] {
  if (!record(value) || !Array.isArray(value.stocks) || !value.stocks.every(item => record(item) && identity(item) && (item.category === 'STOCK' || item.category === 'ETF') && markets.includes(String(item.market)))) {
    throw new Error('종목 검색 응답 형식이 올바르지 않습니다.');
  }
  return value.stocks as Stock[];
}
export function decodePrice(value: unknown): StockPrice {
  if (!record(value) || !identity(value) || typeof value.baseDate !== 'string' || typeof value.closePrice !== 'number' || !Number.isFinite(value.closePrice)) {
    throw new Error('최근 종가 응답 형식이 올바르지 않습니다.');
  }
  return value as StockPrice;
}
export function stockCurrency(stock: { assetCode: string; currency?: unknown }): unknown {
  return stock.currency ?? (stock.assetCode.endsWith('.US') ? 'USD' : 'KRW');
}
export class MarketApi {
  constructor(private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis)) {}
  private async request(path: string, signal?: AbortSignal): Promise<unknown> {
    const response = await this.fetcher(path, { credentials: 'include', signal });
    if (!response.ok) {
      let message = `요청을 처리하지 못했습니다. (HTTP ${response.status})`;
      try {
        const body: unknown = await response.json();
        if (record(body) && typeof body.message === 'string') message = body.message;
      } catch { /* HTTP status remains available if the error body is not JSON. */ }
      throw new Error(message);
    }
    return response.json();
  }
  async search(keyword: string, country: Country, signal?: AbortSignal): Promise<Stock[]> {
    const query = new URLSearchParams({ q: keyword });
    if (country === 'US') query.set('country', country);
    return decodeStocks(await this.request(`/api/stocks?${query}`, signal));
  }
  async price(assetId: number, signal?: AbortSignal): Promise<StockPrice> {
    return decodePrice(await this.request(`/api/stocks/${assetId}/price`, signal));
  }
}
export type MarketState = {
  query: string; country: Country; category: Category; stocks: Stock[]; selected: Stock | null;
  unitPrice: string; dirty: boolean; baseDate: string | null;
  searchStatus: 'idle' | 'loading' | 'ready' | 'error'; priceStatus: 'idle' | 'loading' | 'ready' | 'error';
  searchError: string | null; priceError: string | null;
};
export class MarketController {
  readonly state: MarketState = { query: '', country: 'KR', category: 'ALL', stocks: [], selected: null, unitPrice: '', dirty: false, baseDate: null, searchStatus: 'idle', priceStatus: 'idle', searchError: null, priceError: null };
  private searchGeneration = 0;
  private priceGeneration = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private searchAbort: AbortController | undefined;
  private priceAbort: AbortController | undefined;
  private active = true;
  private disposed = false;
  constructor(private readonly api: Pick<MarketApi, 'search' | 'price'>, private readonly onChange: (state: MarketState) => void, private readonly debounceMs = 250) {}
  get visibleStocks(): Stock[] { return this.state.category === 'ALL' ? this.state.stocks : this.state.stocks.filter(stock => stock.category === this.state.category); }
  private emit(): void { if (!this.disposed && this.active) this.onChange(this.state); }
  private cancelSearch(): void {
    this.searchGeneration++;
    clearTimeout(this.timer); this.timer = undefined;
    this.searchAbort?.abort(); this.searchAbort = undefined;
  }
  private cancelPrice(): void { this.priceGeneration++; this.priceAbort?.abort(); this.priceAbort = undefined; }
  private resetDraft(): void {
    Object.assign(this.state, { selected: null, unitPrice: '', dirty: false, baseDate: null, priceStatus: 'idle', priceError: null });
  }
  setQuery(query: string): void {
    if (this.disposed) return;
    this.state.query = query; this.search();
  }
  setCountry(country: Country): void {
    if (this.disposed || country === this.state.country) return;
    this.cancelPrice(); this.resetDraft(); this.state.country = country; this.search();
  }
  setCategory(category: Category): void { if (!this.disposed) { this.state.category = category; this.emit(); } }
  select(stock: Stock): void {
    if (this.disposed) return;
    this.cancelSearch(); this.cancelPrice(); this.resetDraft();
    Object.assign(this.state, { selected: stock, stocks: [], searchStatus: 'idle', searchError: null });
    this.price();
  }
  clearSelection(): void {
    if (this.disposed) return;
    this.cancelPrice(); this.resetDraft(); this.search();
  }
  setUnitPrice(unitPrice: string): void { if (!this.disposed) { this.state.unitPrice = unitPrice; this.state.dirty = true; this.emit(); } }
  retrySearch(): void { if (!this.disposed) this.search(); }
  retryPrice(): void { if (!this.disposed) this.price(); }
  private search(): void {
    this.cancelSearch();
    Object.assign(this.state, { stocks: [], searchError: null, searchStatus: 'idle' });
    const keyword = this.state.query.trim();
    if (!this.active || this.disposed || this.state.selected || !keyword) { this.emit(); return; }
    this.state.searchStatus = 'loading'; this.emit();
    const generation = this.searchGeneration;
    const country = this.state.country;
    const abort = new AbortController(); this.searchAbort = abort;
    const current = () => !this.disposed && this.active && generation === this.searchGeneration && !abort.signal.aborted;
    this.timer = setTimeout(async () => {
      this.timer = undefined;
      try {
        const stocks = await this.api.search(keyword, country, abort.signal);
        if (current()) { this.state.stocks = stocks; this.state.searchStatus = 'ready'; }
      } catch {
        if (current()) { this.state.searchStatus = 'error'; this.state.searchError = '검색 결과를 불러오지 못했어요. 연결을 확인하고 다시 시도해 주세요.'; }
      } finally { if (current()) { this.searchAbort = undefined; this.emit(); } }
    }, this.debounceMs);
  }
  private price(): void {
    this.cancelPrice();
    if (!this.active || this.disposed || !this.state.selected) { this.emit(); return; }
    Object.assign(this.state, { priceStatus: 'loading', priceError: null }); this.emit();
    const generation = this.priceGeneration;
    const abort = new AbortController(); this.priceAbort = abort;
    const stock = this.state.selected;
    const current = () => !this.disposed && this.active && generation === this.priceGeneration && !abort.signal.aborted;
    void (async () => {
      try {
        const quote = await this.api.price(stock.assetId, abort.signal);
        if (!current()) return;
        if (quote.closePrice <= 0) throw new Error('최근 종가가 없습니다.');
        this.state.baseDate = quote.baseDate;
        if (!this.state.dirty && !this.state.unitPrice) this.state.unitPrice = String(quote.closePrice);
        this.state.priceStatus = 'ready';
      } catch {
        if (current()) {
          Object.assign(this.state, { priceStatus: 'error', baseDate: null, priceError: '최근 종가를 불러오지 못했습니다. 거래 단가를 직접 입력해 주세요.' });
        }
      } finally { if (current()) { this.priceAbort = undefined; this.emit(); } }
    })();
  }
  setActive(active: boolean): void {
    if (this.disposed || active === this.active) return;
    this.active = active;
    if (!active) { this.cancelSearch(); this.cancelPrice(); }
    else if (this.state.selected) this.price();
    else this.search();
  }
  dispose(): void { if (this.disposed) return; this.disposed = true; this.cancelSearch(); this.cancelPrice(); }
}
