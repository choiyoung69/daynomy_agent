import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeStocks, decodePrice, stockCurrency, MarketApi, MarketController } from '../dist/market.js';

const kr = { assetId: 1, assetCode: '005930', name: '삼성전자', category: 'STOCK', market: 'KOSPI' };
const etf = { assetId: 2, assetCode: '069500', name: 'KODEX 200', category: 'ETF', market: 'KOSPI' };
const us = { assetId: 3, assetCode: 'AAPL.US', name: 'Apple', category: 'STOCK', market: 'NASDAQ' };
const quote = (stock=kr, closePrice=71234.5, baseDate='2026-10-27') => ({ assetId: stock.assetId, assetCode: stock.assetCode, name: stock.name, baseDate, closePrice });
const wait = (ms=12) => new Promise(resolve => setTimeout(resolve, ms));
const flush = async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await wait(0); };
const deferred = () => { let resolve, reject; const promise = new Promise((ok, no) => { resolve=ok; reject=no; }); return {promise, resolve, reject}; };
function harness(delay=5) {
  const searches=[], prices=[], changes=[];
  const api={
    search(query,country,signal) { const d=deferred(); searches.push({query,country,signal,...d}); return d.promise; },
    price(assetId,signal) { const d=deferred(); prices.push({assetId,signal,...d}); return d.promise; },
  };
  const c=new MarketController(api, state => changes.push(structuredClone(state)), delay);
  return {c, searches, prices, changes};
}

test('stock guards preserve original seven markets and optional unchecked currency', () => {
  for (const market of ['KOSPI','KOSDAQ','NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS']) {
    assert.equal(decodeStocks({stocks:[{...kr,market,currency:42}]})[0].currency,42);
  }
  assert.deepEqual(decodeStocks({stocks:[]}),[]);
  // Original isStockMarket uses String(value), rather than typeof === string.
  assert.equal(decodeStocks({stocks:[{...kr,market:{toString:()=> 'KOSPI'}}]}).length,1);
});
test('stock JSON boundary rejects invalid root, fields and unsafe identifiers', () => {
  for (const value of [null,[],{}, {stocks:null}, {stocks:{}}, {stocks:[null]}]) assert.throws(()=>decodeStocks(value));
  for (const invalid of [{assetId:0},{assetId:-1},{assetId:1.2},{assetId:Number.MAX_SAFE_INTEGER+1},{assetId:'1'},{assetCode:1},{name:null},{category:'BOND'},{market:'OTC'},{market:null}]) {
    assert.throws(()=>decodeStocks({stocks:[{...kr,...invalid}]}),JSON.stringify(invalid));
  }
});
test('latest-price decoder accepts finite nonpositive price and opaque date strings', () => {
  for (const closePrice of [0,-1,0.125,Number.MAX_VALUE]) assert.equal(decodePrice(quote(kr,closePrice,'not-a-date')).closePrice,closePrice);
  assert.equal(decodePrice({...quote(),currency:{opaque:true}}).currency.opaque,true);
});
test('latest-price decoder rejects unsafe IDs and numeric strings/nonfinite price', () => {
  for (const value of [null,[],{}, {...quote(),assetId:0}, {...quote(),assetId:'1'}, {...quote(),assetId:Number.MAX_SAFE_INTEGER+1}, {...quote(),assetCode:2}, {...quote(),name:2}, {...quote(),baseDate:null}, {...quote(),closePrice:'12'}, {...quote(),closePrice:NaN}, {...quote(),closePrice:Infinity}]) assert.throws(()=>decodePrice(value));
});
test('currency is nullish fallback only and .US is case-sensitive', () => {
  assert.equal(stockCurrency(us),'USD'); assert.equal(stockCurrency(kr),'KRW');
  assert.equal(stockCurrency({assetCode:'a.us'}),'KRW');
  for (const currency of ['',0,false,'EUR']) assert.equal(stockCurrency({...us,currency}),currency);
  assert.equal(stockCurrency({...us,currency:null}),'USD');
});
test('API encodes query, omits KR, passes credentials and exact AbortSignal', async () => {
  const calls=[]; const controller=new AbortController();
  const api=new MarketApi(async (url,init)=> {calls.push({url:String(url),init}); return new Response(JSON.stringify({stocks:[kr]}));});
  await api.search(' 삼성 & +/? ', 'KR', controller.signal);
  const url=new URL(calls[0].url,'http://localhost');
  assert.equal(url.pathname,'/api/stocks'); assert.equal(url.searchParams.get('q'),' 삼성 & +/? '); assert.equal(url.searchParams.has('country'),false);
  assert.equal(calls[0].init.credentials,'include'); assert.equal(calls[0].init.signal,controller.signal);
  await api.search('AAPL','US',controller.signal); assert.equal(new URL(calls[1].url,'http://localhost').searchParams.get('country'),'US');
});
test('price API uses relative path and same credentials/signal', async () => {
  let call; const signal=new AbortController().signal;
  const api=new MarketApi(async (url,init)=> {call={url:String(url),init}; return new Response(JSON.stringify(quote()));});
  assert.equal((await api.price(1,signal)).baseDate,'2026-10-27');
  assert.equal(call.url,'/api/stocks/1/price'); assert.equal(call.init.credentials,'include'); assert.equal(call.init.signal,signal);
});
test('HTTP errors, malformed JSON and invalid successful payload reject without hidden refresh/retry', async () => {
  for (const response of [new Response('{}',{status:401}),new Response('{}',{status:404}),new Response('{}',{status:500}),new Response('broken'),new Response('{}')]) {
    let count=0; const api=new MarketApi(async()=> {count++; return response;});
    await assert.rejects(api.search('x','KR')); assert.equal(count,1);
  }
});
test('abort rejection reaches API caller without converting to success', async () => {
  const api=new MarketApi(async()=> {throw new DOMException('cancelled','AbortError');});
  await assert.rejects(api.search('x','KR'),{name:'AbortError'});
});
test('controller debounces trimmed text and never searches JS whitespace', async () => {
  const {c, searches}=harness(20);
  c.setQuery('first'); await wait(5); c.setQuery('  삼성전자\uFEFF '); await wait(8); assert.equal(searches.length,0);
  await wait(20); assert.equal(searches.length,1); assert.equal(searches[0].query,'삼성전자'); assert.equal(searches[0].country,'KR');
  c.setQuery(' \t\n\uFEFF '); assert.equal(searches[0].signal.aborted,true); await wait(25); assert.equal(searches.length,1); assert.equal(c.state.searchStatus,'idle'); c.dispose();
});
test('new search invalidates noncooperative stale success and finally', async () => {
  const {c, searches}=harness(); c.setQuery('old'); await wait(); c.setQuery('new');
  assert.equal(searches[0].signal.aborted,true); await wait(); searches[0].resolve([kr]); await flush();
  assert.deepEqual(c.state.stocks,[]); assert.equal(c.state.searchStatus,'loading'); assert.equal(c.state.searchError,null);
  searches[1].resolve([us]); await flush(); assert.deepEqual(c.state.stocks,[us]); assert.equal(c.state.searchStatus,'ready'); c.dispose();
});
test('stale search rejection/finally cannot corrupt a newer loading or ready result', async () => {
  const {c, searches}=harness(); c.setQuery('old'); await wait(); c.setQuery('new'); await wait();
  searches[1].resolve([us]); await flush(); searches[0].reject(new Error('stale failure')); await flush();
  assert.equal(c.state.searchStatus,'ready'); assert.equal(c.state.searchError,null); assert.deepEqual(c.state.stocks,[us]); c.dispose();
});
test('category filtering is local and does not refetch or truncate API results', async () => {
  const {c,searches}=harness(); c.setQuery('fund'); await wait(); searches[0].resolve([kr,etf]); await flush();
  c.setCategory('ETF'); assert.deepEqual(c.visibleStocks,[etf]); c.setCategory('STOCK'); assert.deepEqual(c.visibleStocks,[kr]); c.setCategory('ALL'); assert.deepEqual(c.visibleStocks,[kr,etf]); await wait(); assert.equal(searches.length,1); c.dispose();
});
test('country change cancels search and resets selected draft and starts requested country', async () => {
  const {c,searches,prices}=harness(); c.setQuery('삼성'); await wait(); c.select(kr); assert.equal(searches[0].signal.aborted,true); assert.equal(prices.length,1);
  c.setUnitPrice('0012.3400'); c.setCountry('US'); assert.equal(prices[0].signal.aborted,true);
  assert.equal(c.state.selected,null); assert.equal(c.state.unitPrice,''); assert.equal(c.state.dirty,false); assert.equal(c.state.baseDate,null);
  await wait(); assert.equal(searches.at(-1).country,'US'); c.dispose();
});
test('selection fetches immediately, suspends search, fills positive quote/date without timezone conversion', async () => {
  const {c,prices,searches}=harness(); c.setQuery('삼성'); c.select(kr); assert.equal(prices.length,1); assert.equal(prices[0].assetId,1);
  prices[0].resolve(quote(kr,123.450,'2024-02-29')); await flush(); assert.equal(c.state.unitPrice,'123.45'); assert.equal(c.state.baseDate,'2024-02-29'); assert.equal(c.state.priceStatus,'ready'); assert.equal(c.state.dirty,false);
  c.setQuery('other'); await wait(); assert.equal(searches.length,0); c.dispose();
});
for (const input of ['0001.2300000000000000001','', '9007199254740993.01']) {
  test(`manual price including deletion remains exact after late successful quote (${JSON.stringify(input)})`, async () => {
    const {c,prices}=harness(); c.select(kr); c.setUnitPrice(input); assert.equal(c.state.dirty,true);
    prices[0].resolve(quote()); await flush(); assert.equal(c.state.unitPrice,input); assert.equal(c.state.dirty,true); c.dispose();
  });
}
test('late quote for different stock cannot overwrite newer price or status', async () => {
  const {c,prices}=harness(); c.select(kr); c.select(us); assert.equal(prices[0].signal.aborted,true);
  prices[0].resolve(quote()); await flush(); assert.equal(c.state.unitPrice,''); assert.equal(c.state.priceStatus,'loading'); assert.equal(c.state.selected.assetId,3);
  prices[1].resolve(quote(us,201.12)); await flush(); assert.equal(c.state.unitPrice,'201.12'); c.dispose();
});
test('late price rejection/finally cannot corrupt newer successful quote', async () => {
  const {c,prices}=harness(); c.select(kr); c.select(us); prices[1].resolve(quote(us,201)); await flush(); prices[0].reject(new Error('old')); await flush();
  assert.equal(c.state.priceStatus,'ready'); assert.equal(c.state.priceError,null); assert.equal(c.state.unitPrice,'201'); c.dispose();
});
for (const price of [0,-10]) test(`nonpositive quote ${price} requires manual input, date null and explicit retry`,async()=>{
  const {c,prices}=harness(); c.select(kr); prices[0].resolve(quote(kr,price)); await flush();
  assert.equal(c.state.unitPrice,''); assert.equal(c.state.baseDate,null); assert.equal(c.state.priceStatus,'error'); assert.match(c.state.priceError,/직접|수동/); await wait(); assert.equal(prices.length,1);
  c.retryPrice(); assert.equal(prices.length,2); prices[1].resolve(quote()); await flush(); assert.equal(c.state.unitPrice,'71234.5'); c.dispose();
});
test('network quote error preserves manual input and explicit retry does not overwrite it',async()=>{
  const {c,prices}=harness(); c.select(kr); c.setUnitPrice('42.000'); prices[0].reject(new Error('offline')); await flush();
  assert.equal(c.state.unitPrice,'42.000'); assert.equal(c.state.baseDate,null); assert.equal(c.state.priceStatus,'error'); assert.match(c.state.priceError,/직접|수동/);
  c.retryPrice(); prices[1].resolve(quote()); await flush(); assert.equal(c.state.unitPrice,'42.000'); c.dispose();
});
test('search errors expose retry and do not spin automatic requests',async()=>{
  const {c,searches}=harness(); c.setQuery('삼성'); await wait(); searches[0].reject(new Error('offline')); await flush();
  assert.equal(c.state.searchStatus,'error'); assert.ok(c.state.searchError); await wait(20); assert.equal(searches.length,1);
  c.retrySearch(); await wait(); assert.equal(searches.length,2); searches[1].resolve([]); await flush(); assert.equal(c.state.searchStatus,'ready'); assert.deepEqual(c.visibleStocks,[]); c.dispose();
});
test('clear selection resets draft, cancels quote and resumes current query',async()=>{
  const {c,prices,searches}=harness(); c.setQuery('삼성'); c.select(kr); c.setUnitPrice('77'); c.clearSelection();
  assert.equal(prices[0].signal.aborted,true); assert.equal(c.state.selected,null); assert.equal(c.state.unitPrice,''); assert.equal(c.state.dirty,false); assert.equal(c.state.baseDate,null);
  prices[0].resolve(quote()); await flush(); assert.equal(c.state.unitPrice,''); await wait(); assert.equal(searches.length,1); c.dispose();
});
test('inactive invalidates timers and noncooperative quote, retains draft and resumes selected request',async()=>{
  const {c,prices,searches,changes}=harness(); c.setQuery('삼성'); c.select(kr); c.setUnitPrice('1.000'); c.setActive(false);
  assert.equal(prices[0].signal.aborted,true); const count=changes.length; prices[0].resolve(quote()); await flush(); assert.equal(changes.length,count); assert.equal(c.state.unitPrice,'1.000'); assert.equal(c.state.selected.assetId,1);
  await wait(); assert.equal(searches.length,0); c.setActive(true); assert.equal(prices.length,2); prices[1].resolve(quote()); await flush(); assert.equal(c.state.unitPrice,'1.000'); c.dispose();
});
test('inactive search discards stale error and re-queries only after becoming active',async()=>{
  const {c,searches,changes}=harness(); c.setQuery('삼성'); await wait(); c.setActive(false); assert.equal(searches[0].signal.aborted,true); const count=changes.length;
  searches[0].reject(new Error('old')); await flush(); assert.equal(changes.length,count); c.setActive(true); await wait(); assert.equal(searches.length,2); c.dispose();
});
test('dispose cancels timer/inflight and permanently blocks callbacks and restarts',async()=>{
  const a=harness(); a.c.setQuery('삼성'); a.c.dispose(); await wait(); assert.equal(a.searches.length,0);
  const {c,prices,searches,changes}=harness(); c.select(kr); c.dispose(); assert.equal(prices[0].signal.aborted,true); const count=changes.length;
  prices[0].resolve(quote()); await flush(); c.setActive(true); c.setQuery('apple'); c.retryPrice(); c.retrySearch(); await wait(); assert.equal(changes.length,count); assert.equal(prices.length,1); assert.equal(searches.length,0);
});
test('repeated active values are idempotent and never duplicate in-flight requests',async()=>{
  const {c,prices}=harness(); c.select(kr); c.setActive(true); c.setActive(true); assert.equal(prices.length,1);
  c.setActive(false); c.setActive(false); c.setActive(true); c.setActive(true); assert.equal(prices.length,2); c.dispose();
});
