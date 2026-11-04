import {ServiceClient, endpoint, decodeStocks, decodePrice, decodeNewsPage} from './core.ts';
import type {Stock} from './core.ts';

export * from './core.ts';
export type Query = Record<string, string | number | boolean | undefined>;
export type RequestOptions = {method?: string; query?: Query; body?: unknown; csrf?: boolean; signal?: AbortSignal; retryUnauthorized?: boolean};
export type CallOptions = {id?: number; secondaryId?: number; query?: Query; body?: unknown; signal?: AbortSignal};

/** API cookies belong to the native networking session. They are never copied into app storage. */
export class APIClient {
  readonly baseURL: string;
  private client: ServiceClient;
  constructor(options: {baseURL: string; fetchImpl?: typeof fetch; timeoutMs?: number}) {
    this.baseURL = options.baseURL.replace(/\/$/, '');
    this.client = new ServiceClient(this.baseURL, options.fetchImpl ?? fetch, options.timeoutMs);
  }
  invalidateSession(): void {this.client.invalidateSession();}
  request(path: string, options: RequestOptions = {}): Promise<unknown> {
    const query = Object.fromEntries(Object.entries(options.query ?? {}).filter(([, v]) => v !== undefined).map(([k,v]) => [k, String(v)]));
    return this.client.request(path, {...options, query});
  }
  call(name: string, options: CallOptions = {}): Promise<unknown> {
    const route = endpoint(name, options.id, options.secondaryId);
    return this.request(route.path, {method: route.method, csrf: route.csrf, query: options.query, body: options.body, signal: options.signal});
  }
  async searchStocks(q: string, country: 'KR' | 'US' = 'KR', signal?: AbortSignal): Promise<Stock[]> {
    const keyword = q.trim();
    if (!keyword || [...keyword].length > 50 || !/[\p{L}\p{N}]/u.test(keyword)) throw new Error('종목 이름이나 코드를 50자 이내로 입력해 주세요.');
    return decodeStocks(await this.request('/api/stocks', {query:{q: keyword, country}, signal}));
  }
  async stockPrice(assetId: number, signal?: AbortSignal) {
    if (!Number.isSafeInteger(assetId) || assetId <= 0) throw new Error('종목 ID를 확인해 주세요.');
    return decodePrice(await this.request(`/api/stocks/${assetId}/price`, {signal}));
  }
  async news(query: Query = {}, signal?: AbortSignal) {
    return decodeNewsPage(await this.call('news', {query, signal}));
  }
  portfolio(signal?: AbortSignal) {return this.call('portfolio', {signal});}
  calculate(holdings: unknown[], signal?: AbortSignal) {return this.call('calculate', {body:{holdings}, signal});}
  calendar(year: number, month: number, scope: 'ALL' | 'PORTFOLIO', member: boolean, holdings: unknown[] = [], signal?: AbortSignal) {
    return this.call(member ? 'calendar' : 'guestCalendar', {query:{year, month, scope}, ...(member ? {} : {body:{holdings}}), signal});
  }
  analysis(member: boolean, assets: unknown[] = [], refresh = false) {
    return this.call(member ? (refresh ? 'refreshAnalysis' : 'updateAnalysis') : 'guestAnalysis', member ? {} : {body:{assets}});
  }
}
