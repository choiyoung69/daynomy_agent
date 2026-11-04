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
  async todayNews(signal?: AbortSignal) {
    const page=decodeNewsPage(await this.call('today', {signal}));
    if(page.page<1||page.size<1||page.totalPages<0||page.totalElements<0||page.items.length>9) throw new Error('오늘 뉴스 응답이 올바르지 않습니다.');
    return page;
  }
  async searchNews(q: string, options: {page?:number; category?:string; sort?:string} = {}, signal?:AbortSignal) {
    if (!q.trim() || q.length>100 || !/[\p{L}\p{N}]/u.test(q) || /[\r\n\u0085\u2028\u2029]/u.test(q)) throw new Error('검색어는 문자나 숫자를 포함해 100자 이내로 입력해 주세요.');
    const page=options.page??1, sort=options.sort??'LATEST';
    if (!Number.isSafeInteger(page)||page<1||!['LATEST','RELEVANCE'].includes(sort)) throw new Error('검색 조건을 확인해 주세요.');
    const raw:any=await this.call('newsSearch',{query:{q,page,size:20,sort,...(options.category&&options.category!=='ALL'?{category:options.category}:{})},signal});
    if (!raw||!Array.isArray(raw.content)||raw.page<1||raw.size<1||raw.totalPages<0||raw.totalElements<0) throw new Error('뉴스 검색 응답이 올바르지 않습니다.');
    return decodeNewsPage({...raw,items:raw.content,hasNext:raw.page<raw.totalPages});
  }
  async updateHolding(id:number, quantity:string, averagePurchasePrice:string) {
    if (!/^\d+$/.test(quantity)||!Number.isSafeInteger(Number(quantity))||Number(quantity)<=0) throw new Error('수량은 1주 이상의 정수로 입력해 주세요.');
    if (!/^\d{1,15}(?:\.\d{1,2})?$/.test(averagePurchasePrice)||Number(averagePurchasePrice)<0.01) throw new Error('원화 평균 매입가는 0.01원 이상, 소수 둘째 자리까지 입력해 주세요.');
    return this.call('updateHolding',{id,body:{quantity:Number(quantity),averagePurchasePrice}});
  }
  deleteHolding(id:number) {return this.call('deleteHolding',{id});}
  portfolio(signal?: AbortSignal) {return this.call('portfolio', {signal});}
  calculate(holdings: unknown[], signal?: AbortSignal) {return this.call('calculate', {body:{holdings}, signal});}
  calendar(year: number, month: number, scope: 'ALL' | 'PORTFOLIO', member: boolean, holdings: unknown[] = [], signal?: AbortSignal) {
    return this.call(member ? 'calendar' : 'guestCalendar', {query:{year, month, scope}, ...(member ? {} : {body:{holdings}}), signal});
  }
  analysis(member: boolean, assets: unknown[] = [], refresh = false) {
    return this.call(member ? (refresh ? 'refreshAnalysis' : 'updateAnalysis') : 'guestAnalysis', member ? {} : {body:{assets}});
  }
}
