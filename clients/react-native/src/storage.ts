import {replayLedger, validateTrade} from './core.ts';
import type {Trade} from './core.ts';
export interface KeyValueStore {getItem(key:string):Promise<string|null>;setItem(key:string,value:string):Promise<void>;removeItem(key:string):Promise<void>}
export const GUEST_STORAGE_KEY='daynomy.rn.guest-ledger.v1';
export function todayInSeoul():string {
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
  return ['year','month','day'].map(key=>parts.find(part=>part.type===key)?.value).join('-');
}
const clone=(trade:Trade):Trade=>({...trade,stock:{...trade.stock}});
/** Device-local guest records only. No account data or authentication secrets are stored here. */
export class GuestLedgerStore {
  private records:Trade[]=[];
  private adapter:KeyValueStore;
  private pending:Promise<void>=Promise.resolve();
  get trades():Trade[]{return this.records.map(clone);}
  constructor(adapter:KeyValueStore){this.adapter=adapter;}
  private queue<T>(work:()=>Promise<T>):Promise<T> {
    const result=this.pending.then(work,work);
    this.pending=result.then(()=>{},()=>{});
    return result;
  }
  load():Promise<Trade[]> {return this.queue(async()=>{
    const saved=await this.adapter.getItem(GUEST_STORAGE_KEY);
    if(!saved){this.records=[];return [];}
    try {
      const parsed:unknown=JSON.parse(saved);
      if(!parsed||typeof parsed!=='object'||!('version' in parsed)||parsed.version!==1||!('trades' in parsed)||!Array.isArray(parsed.trades))throw new Error('INVALID_STORAGE');
      const trades=parsed.trades as Trade[];
      trades.forEach(trade=>validateTrade(trade,todayInSeoul()));replayLedger(trades);
      this.records=trades.map(clone);return this.trades;
    } catch {throw new Error('저장된 게스트 거래를 읽지 못했어요. 원본은 기기에 보존했으니 초기화 전에 확인해 주세요.');}
  });}
  private save(transform:(previous:Trade[])=>Trade[]):Promise<void> {return this.queue(async()=>{
    const next=transform(this.records.map(clone));
    next.forEach(trade=>validateTrade(trade,todayInSeoul()));replayLedger(next);
    await this.adapter.setItem(GUEST_STORAGE_KEY,JSON.stringify({version:1,trades:next}));
    this.records=next;
  });}
  add(trade:Trade):Promise<void> {const copy=clone(trade);return this.save(previous=>[...previous,copy]);}
  update(trade:Trade):Promise<void> {const copy=clone(trade);return this.save(previous=>{
    const old=previous.find(item=>item.id===copy.id);
    if(!old||old.stock.assetId!==copy.stock.assetId||old.type!==copy.type)throw new Error('거래 종목과 매수·매도 유형은 수정할 수 없어요.');
    return previous.map(item=>item.id===copy.id?copy:item);
  });}
  remove(id:number):Promise<void> {return this.save(previous=>previous.filter(trade=>trade.id!==id));}
  clear():Promise<void> {return this.queue(async()=>{await this.adapter.removeItem(GUEST_STORAGE_KEY);this.records=[];});}
  holdings(){return replayLedger(this.records);}
}
