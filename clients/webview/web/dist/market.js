const markets = ['KOSPI', 'KOSDAQ', 'NASDAQ', 'NYSE', 'NYSE_ARCA', 'NYSE_AMERICAN', 'BATS'];
function record(value) { return typeof value === 'object' && value !== null; }
function identity(value) {
    return Number.isSafeInteger(value.assetId) && Number(value.assetId) > 0 && typeof value.assetCode === 'string' && typeof value.name === 'string';
}
export function decodeStocks(value) {
    if (!record(value) || !Array.isArray(value.stocks) || !value.stocks.every(item => record(item) && identity(item) && (item.category === 'STOCK' || item.category === 'ETF') && markets.includes(String(item.market)))) {
        throw new Error('종목 검색 응답 형식이 올바르지 않습니다.');
    }
    return value.stocks;
}
export function decodePrice(value) {
    if (!record(value) || !identity(value) || typeof value.baseDate !== 'string' || typeof value.closePrice !== 'number' || !Number.isFinite(value.closePrice)) {
        throw new Error('최근 종가 응답 형식이 올바르지 않습니다.');
    }
    return value;
}
export function stockCurrency(stock) {
    return stock.currency ?? (stock.assetCode.endsWith('.US') ? 'USD' : 'KRW');
}
export class MarketApi {
    fetcher;
    constructor(fetcher = globalThis.fetch.bind(globalThis)) {
        this.fetcher = fetcher;
    }
    async request(path, signal) {
        const response = await this.fetcher(path, { credentials: 'include', signal });
        if (!response.ok) {
            let message = `요청을 처리하지 못했습니다. (HTTP ${response.status})`;
            try {
                const body = await response.json();
                if (record(body) && typeof body.message === 'string')
                    message = body.message;
            }
            catch { /* HTTP status remains available if the error body is not JSON. */ }
            throw new Error(message);
        }
        return response.json();
    }
    async search(keyword, country, signal) {
        const query = new URLSearchParams({ q: keyword });
        if (country === 'US')
            query.set('country', country);
        return decodeStocks(await this.request(`/api/stocks?${query}`, signal));
    }
    async price(assetId, signal) {
        return decodePrice(await this.request(`/api/stocks/${assetId}/price`, signal));
    }
}
export class MarketController {
    api;
    onChange;
    debounceMs;
    state = { query: '', country: 'KR', category: 'ALL', stocks: [], selected: null, unitPrice: '', dirty: false, baseDate: null, searchStatus: 'idle', priceStatus: 'idle', searchError: null, priceError: null };
    searchGeneration = 0;
    priceGeneration = 0;
    timer;
    searchAbort;
    priceAbort;
    active = true;
    disposed = false;
    constructor(api, onChange, debounceMs = 250) {
        this.api = api;
        this.onChange = onChange;
        this.debounceMs = debounceMs;
    }
    get visibleStocks() { return this.state.category === 'ALL' ? this.state.stocks : this.state.stocks.filter(stock => stock.category === this.state.category); }
    emit() { if (!this.disposed && this.active)
        this.onChange(this.state); }
    cancelSearch() {
        this.searchGeneration++;
        clearTimeout(this.timer);
        this.timer = undefined;
        this.searchAbort?.abort();
        this.searchAbort = undefined;
    }
    cancelPrice() { this.priceGeneration++; this.priceAbort?.abort(); this.priceAbort = undefined; }
    resetDraft() {
        Object.assign(this.state, { selected: null, unitPrice: '', dirty: false, baseDate: null, priceStatus: 'idle', priceError: null });
    }
    setQuery(query) {
        if (this.disposed)
            return;
        this.state.query = query;
        this.search();
    }
    setCountry(country) {
        if (this.disposed || country === this.state.country)
            return;
        this.cancelPrice();
        this.resetDraft();
        this.state.country = country;
        this.search();
    }
    setCategory(category) { if (!this.disposed) {
        this.state.category = category;
        this.emit();
    } }
    select(stock) {
        if (this.disposed)
            return;
        this.cancelSearch();
        this.cancelPrice();
        this.resetDraft();
        Object.assign(this.state, { selected: stock, stocks: [], searchStatus: 'idle', searchError: null });
        this.price();
    }
    clearSelection() {
        if (this.disposed)
            return;
        this.cancelPrice();
        this.resetDraft();
        this.search();
    }
    setUnitPrice(unitPrice) { if (!this.disposed) {
        this.state.unitPrice = unitPrice;
        this.state.dirty = true;
        this.emit();
    } }
    retrySearch() { if (!this.disposed)
        this.search(); }
    retryPrice() { if (!this.disposed)
        this.price(); }
    search() {
        this.cancelSearch();
        Object.assign(this.state, { stocks: [], searchError: null, searchStatus: 'idle' });
        const keyword = this.state.query.trim();
        if (!this.active || this.disposed || this.state.selected || !keyword) {
            this.emit();
            return;
        }
        this.state.searchStatus = 'loading';
        this.emit();
        const generation = this.searchGeneration;
        const country = this.state.country;
        const abort = new AbortController();
        this.searchAbort = abort;
        const current = () => !this.disposed && this.active && generation === this.searchGeneration && !abort.signal.aborted;
        this.timer = setTimeout(async () => {
            this.timer = undefined;
            try {
                const stocks = await this.api.search(keyword, country, abort.signal);
                if (current()) {
                    this.state.stocks = stocks;
                    this.state.searchStatus = 'ready';
                }
            }
            catch {
                if (current()) {
                    this.state.searchStatus = 'error';
                    this.state.searchError = '검색 결과를 불러오지 못했어요. 연결을 확인하고 다시 시도해 주세요.';
                }
            }
            finally {
                if (current()) {
                    this.searchAbort = undefined;
                    this.emit();
                }
            }
        }, this.debounceMs);
    }
    price() {
        this.cancelPrice();
        if (!this.active || this.disposed || !this.state.selected) {
            this.emit();
            return;
        }
        Object.assign(this.state, { priceStatus: 'loading', priceError: null });
        this.emit();
        const generation = this.priceGeneration;
        const abort = new AbortController();
        this.priceAbort = abort;
        const stock = this.state.selected;
        const current = () => !this.disposed && this.active && generation === this.priceGeneration && !abort.signal.aborted;
        void (async () => {
            try {
                const quote = await this.api.price(stock.assetId, abort.signal);
                if (!current())
                    return;
                if (quote.closePrice <= 0)
                    throw new Error('최근 종가가 없습니다.');
                this.state.baseDate = quote.baseDate;
                if (!this.state.dirty && !this.state.unitPrice)
                    this.state.unitPrice = String(quote.closePrice);
                this.state.priceStatus = 'ready';
            }
            catch {
                if (current()) {
                    Object.assign(this.state, { priceStatus: 'error', baseDate: null, priceError: '최근 종가를 불러오지 못했습니다. 거래 단가를 직접 입력해 주세요.' });
                }
            }
            finally {
                if (current()) {
                    this.priceAbort = undefined;
                    this.emit();
                }
            }
        })();
    }
    setActive(active) {
        if (this.disposed || active === this.active)
            return;
        this.active = active;
        if (!active) {
            this.cancelSearch();
            this.cancelPrice();
        }
        else if (this.state.selected)
            this.price();
        else
            this.search();
    }
    dispose() { if (this.disposed)
        return; this.disposed = true; this.cancelSearch(); this.cancelPrice(); }
}
