import {routes} from './routes.ts';
export type Stock = {assetId:number;assetCode:string;name:string;category:'STOCK'|'ETF';market:string;currency?:'KRW'|'USD'};
export type Trade = {id:number;stock:Stock;type:'BUY'|'SELL';date:string;quantity:number;unitPrice:string;fee:string;tax:string;exchangeRate?:string};
export type Endpoint = {path:string;method:string;csrf:boolean};
export type RequestOptions = {method?:string;body?:unknown;csrf?:boolean;query?:Record<string,string>;retryUnauthorized?:boolean;signal?:AbortSignal};
export class ApiError extends Error {
  readonly status:number;readonly code?:string;
  constructor(status:number,code?:string,message='요청을 처리하지 못했습니다.') {super(message);this.name='ApiError';this.status=status;this.code=code;}
}
const record=(value:unknown):value is Record<string,unknown>=>typeof value==='object'&&value!==null&&!Array.isArray(value);
const validId=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>0;
const markets=new Set(['KOSPI','KOSDAQ','NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS']);
export function endpoint(name:string,id?:number,secondaryId?:number):Endpoint {
  const route=routes[name];
  if (!route) throw new Error('지원하지 않는 API입니다.');
  let path=route.path;
  for (const [key,value] of [['id',id],['secondaryId',secondaryId]] as const) {
    if(path.includes(`{${key}}`)) {
      if(!validId(value)) throw new Error('ID는 안전한 양의 정수여야 합니다.');
      path=path.replace(`{${key}}`,String(value));
    }
  }
  return {...route,path};
}
export function buildURL(base:string,path:string,query:Record<string,string>={}):string {
  const origin=new URL(base);
  if (!['http:','https:'].includes(origin.protocol)||origin.username||origin.password||origin.search||origin.hash||!path.startsWith('/')||path.startsWith('//')||path.includes('\\')) throw new Error('API 주소를 확인해 주세요.');
  if(origin.protocol==='http:'&&!['localhost','127.0.0.1','[::1]','10.0.2.2'].includes(origin.hostname))throw new Error('로컬 개발 서버 외에는 HTTPS 주소를 사용해 주세요.');
  const target=new URL(path,origin.origin);
  if(target.origin!==origin.origin) throw new Error('다른 서버로 요청할 수 없어요.');
  Object.entries(query).forEach(([key,value])=>target.searchParams.set(key,value));
  return target.toString();
}

const amountKeys=new Set(['unitPrice','fee','tax','exchangeRate','averagePurchasePrice']);
/** Serialize editor decimal strings as JSON numeric tokens without an intermediate binary float. */
export function encodeBody(body:unknown):string {
  const seen=new Set<object>();
  const encode=(value:unknown,key?:string):string=>{
    if(typeof value==='string') {
      if(key&&amountKeys.has(key)) {
        if(!/^\d{1,15}(\.\d{1,6})?$/.test(value))throw new Error('금액 형식을 확인해 주세요.');
        return value.replace(/^0+(?=\d)/,'');
      }
      return JSON.stringify(value);
    }
    if(value===null)return 'null';
    if(typeof value==='number'){if(!Number.isFinite(value))throw new Error('유효하지 않은 숫자입니다.');return JSON.stringify(value);}
    if(typeof value==='boolean')return String(value);
    if(Array.isArray(value)){if(seen.has(value))throw new Error('순환 데이터입니다.');seen.add(value);const result='['+value.map(item=>encode(item)).join(',')+']';seen.delete(value);return result;}
    if(record(value)){if(seen.has(value))throw new Error('순환 데이터입니다.');seen.add(value);const result='{'+Object.entries(value).filter(([,item])=>item!==undefined).map(([name,item])=>JSON.stringify(name)+':'+encode(item,name)).join(',')+'}';seen.delete(value);return result;}
    throw new Error('전송할 수 없는 데이터입니다.');
  };
  return encode(body);
}

export class ServiceClient {
  private base:string;private transport:typeof fetch;private refreshPromise:Promise<void>|null=null;private generation=0;private timeoutMs:number;
  constructor(base:string,transport:typeof fetch=fetch,timeoutMs=20000){buildURL(base,'/');this.base=base;this.transport=transport;this.timeoutMs=timeoutMs;}
  invalidateSession(){this.generation++;}
  private async send(path:string,options:RequestOptions,headers:Headers):Promise<Response> {
    if(options.signal?.aborted)throw options.signal.reason??new Error('요청이 취소되었습니다.');
    const transport=this.transport;
    return transport(buildURL(this.base,path,options.query),{method:options.method??'GET',credentials:'include',headers,signal:options.signal,...(options.body!==undefined?{body:encodeBody(options.body)}:{})});
  }
  private async csrf(signal?:AbortSignal):Promise<Headers> {
    const value=await this.request('/api/auth/csrf',{retryUnauthorized:false,signal});
    if(!record(value)||typeof value.headerName!=='string'||!/^X-[!#$%&'*+.^_`|~0-9A-Za-z-]+$/i.test(value.headerName)||typeof value.token!=='string'||!value.token||/[\r\n]/.test(value.token)) throw new ApiError(0,'INVALID_CSRF','CSRF 응답 형식이 올바르지 않습니다.');
    const headers=new Headers();headers.set(value.headerName,value.token);return headers;
  }
  private async refresh():Promise<void> {
    if(!this.refreshPromise) {
      const generation=this.generation;
      this.refreshPromise=(async()=>{
        await this.request('/api/auth/refresh',{method:'POST',csrf:true,retryUnauthorized:false});
        if(generation!==this.generation) throw new ApiError(401,'SESSION_CHANGED','로그인 상태가 변경되었어요.');
      })().finally(()=>{this.refreshPromise=null;});
    }
    return this.refreshPromise;
  }
  async request(path:string,options:RequestOptions={}):Promise<any> {
    const controller=new AbortController();
    const cancel=()=>controller.abort(options.signal?.reason);
    if(options.signal?.aborted)cancel();else options.signal?.addEventListener('abort',cancel,{once:true});
    const timer=setTimeout(()=>controller.abort(new Error('요청 시간이 초과되었습니다. 다시 시도해 주세요.')),this.timeoutMs);
    try{return await this.requestOnce(path,{...options,signal:controller.signal});}
    finally{clearTimeout(timer);options.signal?.removeEventListener('abort',cancel);}
  }
  private async requestOnce(path:string,options:RequestOptions={}):Promise<any> {
    const epoch=this.generation;
    const method=(options.method??'GET').toUpperCase();
    const headers=options.csrf?await this.csrf(options.signal):new Headers();
    headers.set('Accept','application/json');if(options.body!==undefined) headers.set('Content-Type','application/json');
    const response=await this.send(path,{...options,method},headers);
    if(epoch!==this.generation)throw new ApiError(401,'SESSION_CHANGED','로그인 상태가 변경되었어요.');
    if(response.status===401&&['GET','HEAD'].includes(method)&&options.retryUnauthorized!==false&&path!=='/api/auth/csrf') {
      await this.refresh();
      return this.request(path,{...options,retryUnauthorized:false});
    }
    if(!response.ok) {
      let code:string|undefined;let message:string|undefined;
      try {const body:unknown=await response.json();if(record(body)){if(typeof body.code==='string')code=body.code;if(typeof body.message==='string')message=body.message;}} catch {}
      throw new ApiError(response.status,code,message);
    }
    if(response.status===204) return null;
    try {const value=await response.json();if(epoch!==this.generation)throw new ApiError(401,'SESSION_CHANGED','로그인 상태가 변경되었어요.');return value;} catch(error) {if(error instanceof ApiError)throw error;throw new ApiError(response.status,'INVALID_RESPONSE','서버 응답 형식을 확인하지 못했어요.');}
  }
}
function isStock(value:unknown):value is Stock {
  return record(value)&&validId(value.assetId)&&typeof value.assetCode==='string'&&typeof value.name==='string'&&(value.category==='STOCK'||value.category==='ETF')&&typeof value.market==='string'&&markets.has(value.market)&&(value.currency===undefined||value.currency==='KRW'||value.currency==='USD');
}
export function decodeStocks(raw:unknown):Stock[] {
  if(!record(raw)||!Array.isArray(raw.stocks)||!raw.stocks.every(isStock))throw new Error('종목 검색 응답 형식이 올바르지 않습니다.');
  return raw.stocks;
}
export function decodePrice(raw:unknown):{assetId:number;assetCode:string;name:string;baseDate:string;closePrice:number;currency?:string} {
  if(!record(raw)||!validId(raw.assetId)||typeof raw.assetCode!=='string'||typeof raw.name!=='string'||typeof raw.baseDate!=='string'||typeof raw.closePrice!=='number'||!Number.isFinite(raw.closePrice))throw new Error('최근 종가 응답 형식이 올바르지 않습니다.');
  return raw as {assetId:number;assetCode:string;name:string;baseDate:string;closePrice:number};
}
export function decodeNewsPage(raw:unknown):{items:any[];page:number;hasNext:boolean;size:number;totalPages:number;totalElements:number} {
  const categories=new Set(['REAL_ESTATE','DEPOSIT_SAVINGS','STOCK','ECONOMY','ETF','BOND','PENSION','FOREIGN_EXCHANGE','VIRTUAL_ASSET','GOLD']);
  if(!record(raw)||!Array.isArray(raw.items)||!raw.items.every(item=>record(item)&&validId(item.id)&&typeof item.title==='string'&&typeof item.category==='string'&&categories.has(item.category)&&(item.imageUrl===null||typeof item.imageUrl==='string')&&(item.publishedAt===null||typeof item.publishedAt==='string'))||!Number.isInteger(raw.page)||!Number.isInteger(raw.size)||!Number.isInteger(raw.totalPages)||!Number.isInteger(raw.totalElements)||typeof raw.hasNext!=='boolean')throw new Error('뉴스 응답 형식이 올바르지 않습니다.');
  return raw as {items:any[];page:number;hasNext:boolean;size:number;totalPages:number;totalElements:number};
}
export function stockCurrency(stock:Stock):'KRW'|'USD' {return stock.currency??(stock.assetCode.endsWith('.US')||!['KOSPI','KOSDAQ'].includes(stock.market)?'USD':'KRW');}
function scaled(text:string,scale:number):bigint {
  const [whole,fraction='']=text.split('.');
  return BigInt(whole)*10n**BigInt(scale)+BigInt((fraction+'0'.repeat(scale)).slice(0,scale));
}
function roundDivide(numerator:bigint,denominator:bigint):bigint {return (numerator+(numerator<0n?-denominator/2n:denominator/2n))/denominator;}
function money(cents:bigint):string {const negative=cents<0n;const value=negative?-cents:cents;return `${negative?'-':''}${value/100n}.${String(value%100n).padStart(2,'0')}`;}
export function validateTrade(trade:Trade,today:string):void {
  if(!record(trade)||!validId(trade.id)||!isStock(trade.stock)||!['BUY','SELL'].includes(trade.type))throw new Error('거래 정보를 확인해 주세요.');
  const date=new Date(`${trade.date}T00:00:00Z`);
  if(!/^\d{4}-\d{2}-\d{2}$/.test(trade.date)||!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==trade.date||trade.date>today)throw new Error('거래일은 오늘 또는 과거의 올바른 날짜여야 합니다.');
  if(!validId(trade.quantity))throw new Error('수량은 1주 이상의 정수여야 합니다.');
  for(const key of ['unitPrice','fee','tax'] as const) {
    const value=trade[key];const scale=key==='unitPrice'?4:2;
    if(typeof value!=='string'||!(new RegExp(`^\\d{1,15}(\\.\\d{1,${scale}})?$`)).test(value))throw new Error('단가·수수료·세금의 소수 자릿수를 확인해 주세요.');
    if(key==='unitPrice'&&scaled(value,4)<(stockCurrency(trade.stock)==='USD'?1n:100n))throw new Error('거래 단가를 확인해 주세요.');
  }
  if((stockCurrency(trade.stock)==='USD'||trade.exchangeRate!==undefined)&&(typeof trade.exchangeRate!=='string'||!/^\d{1,10}(\.\d{1,6})?$/.test(trade.exchangeRate)||scaled(trade.exchangeRate,6)<=0n))throw new Error('미국 종목의 양수 환율을 입력해 주세요.');
}
export function replayLedger(trades:Trade[]):{holdings:{assetId:number;quantity:number;averagePurchasePrice:string}[];realizedProfitLoss:string} {
  const positions=new Map<number,{assetId:number;quantity:number;cost:bigint}>();
  const ids=new Set<number>();let profit=0n;
  const ordered=[...trades].sort((a,b)=>a.date.localeCompare(b.date)||a.id-b.id);
  for(const trade of ordered) {
    validateTrade(trade,'9999-12-31');if(ids.has(trade.id))throw new Error('거래 ID가 중복됩니다.');ids.add(trade.id);
    const current=positions.get(trade.stock.assetId);const oldQuantity=current?.quantity??0;const oldCost=current?.cost??0n;
    const gross=scaled(trade.unitPrice,4)*BigInt(trade.quantity);
    const costs=scaled(trade.fee,4)+scaled(trade.tax,4);
    const rate=stockCurrency(trade.stock)==='USD'?scaled(trade.exchangeRate!,6):1000000n;
    if(trade.type==='BUY') {
      const quantity=oldQuantity+trade.quantity;if(!Number.isSafeInteger(quantity))throw new Error('보유 수량이 너무 큽니다.');
      const cost=roundDivide(oldCost*BigInt(oldQuantity)*100000000n+(gross+costs)*rate,BigInt(quantity)*100000000n);
      positions.set(trade.stock.assetId,{assetId:trade.stock.assetId,quantity,cost});
    } else {
      if(oldQuantity<trade.quantity)throw new Error('해당 거래일의 보유량보다 많이 매도할 수 없어요.');
      profit+=(gross-costs)*rate-oldCost*BigInt(trade.quantity)*100000000n;
      const quantity=oldQuantity-trade.quantity;if(quantity)positions.set(trade.stock.assetId,{assetId:trade.stock.assetId,quantity,cost:oldCost});else positions.delete(trade.stock.assetId);
    }
  }
  return {holdings:[...positions.values()].map(({assetId,quantity,cost})=>({assetId,quantity,averagePurchasePrice:money(cost)})),realizedProfitLoss:money(roundDivide(profit,100000000n))};
}
export class StockSelection {
  stocks:Stock[]=[];selected:Stock|null=null;unitPrice='';baseDate:string|null=null;
  private searchGeneration=0;private priceGeneration=0;private dirty=false;
  beginSearch():number{return ++this.searchGeneration;}
  resolveSearch(generation:number,stocks:Stock[]):void {if(generation===this.searchGeneration)this.stocks=[...stocks];}
  select(stock:Stock):number {this.selected=stock;this.unitPrice='';this.baseDate=null;this.dirty=false;return ++this.priceGeneration;}
  typePrice(text:string):void {this.unitPrice=text;this.dirty=true;}
  resolvePrice(generation:number,price:{assetId:number;closePrice:number;baseDate:string}):void {
    if(generation!==this.priceGeneration||price.assetId!==this.selected?.assetId)return;
    this.baseDate=price.baseDate;if(!this.dirty&&Number.isFinite(price.closePrice)&&price.closePrice>0)this.unitPrice=String(price.closePrice);
  }
}
