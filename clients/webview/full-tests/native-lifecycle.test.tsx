import React from 'react';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebViewForeground } from '../fullweb/src/hooks/useWebViewForeground';
import { PortfolioTransactionEditor } from '../fullweb/src/features/portfolio/components/PortfolioTransactionEditor';
import { getLatestStockPrice, getUsdKrwRate, searchStocks } from '../fullweb/src/features/stocks/api';
vi.mock('../fullweb/src/features/stocks/api',()=>({getLatestStockPrice:vi.fn(),getUsdKrwRate:vi.fn(),searchStocks:vi.fn()}));
const stock={assetId:1,assetCode:'005930',name:'삼성전자',category:'STOCK',market:'KOSPI'} as const;
function Probe(){const active=useWebViewForeground();return <output aria-label="foreground">{String(active)}</output>;}
function host(detail:unknown){act(()=>{window.dispatchEvent(new CustomEvent('daynomy:active',{detail}));});}
beforeEach(()=>{vi.useFakeTimers();Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});vi.mocked(getLatestStockPrice).mockImplementation(()=>new Promise(()=>{}));vi.mocked(searchStocks).mockImplementation(()=>new Promise(()=>{}));});
afterEach(()=>{cleanup();vi.useRealTimers();vi.resetAllMocks();});
describe('native boolean lifecycle messages (same document, no privileged bridge)',()=>{
  it('boolean false pauses and boolean true resumes foreground state',()=>{const view=render(<Probe/>);expect(view.getByLabelText('foreground').textContent).toBe('true');host(false);expect(view.getByLabelText('foreground').textContent).toBe('false');host(true);expect(view.getByLabelText('foreground').textContent).toBe('true');});
  it('string true and malformed payload cannot resume a paused document',()=>{const view=render(<Probe/>);host(false);for(const detail of ['true','false',1,0,null,{}, {active:true}])host(detail);expect(view.getByLabelText('foreground').textContent).toBe('false');host(true);expect(view.getByLabelText('foreground').textContent).toBe('true');});
  it('false aborts search and true reissues one read after debounce; duplicate true is idempotent',async()=>{
    const save=vi.fn();const view=render(<PortfolioTransactionEditor onClose={vi.fn()} onSave={save}/>);
    fireEvent.change(view.getByPlaceholderText('종목명 또는 종목코드'),{target:{value:'삼성'}});
    await act(async()=>{await vi.advanceTimersByTimeAsync(250);});expect(searchStocks).toHaveBeenCalledTimes(1);
    const firstSignal=vi.mocked(searchStocks).mock.calls[0][1]!;expect(firstSignal.aborted).toBe(false);
    host(false);expect(firstSignal.aborted).toBe(true);
    await act(async()=>{await vi.advanceTimersByTimeAsync(1000);});expect(searchStocks).toHaveBeenCalledTimes(1);
    host(true);await act(async()=>{await vi.advanceTimersByTimeAsync(250);});expect(searchStocks).toHaveBeenCalledTimes(2);
    host(true);host(true);await act(async()=>{await vi.advanceTimersByTimeAsync(1000);});expect(searchStocks).toHaveBeenCalledTimes(2);expect(save).not.toHaveBeenCalled();
  });
  it('price read cancellation/resume preserves manual price and quantity without replaying save',async()=>{
    const pending:Array<{signal:AbortSignal,resolve:(v:unknown)=>void}>=[];
    vi.mocked(getLatestStockPrice).mockImplementation((_id,signal)=>new Promise(resolve=>pending.push({signal:signal!,resolve:resolve as (v:unknown)=>void})));
    const save=vi.fn();const view=render(<PortfolioTransactionEditor stock={stock} onClose={vi.fn()} onSave={save}/>);
    const price=view.getByLabelText('거래 단가 (원)') as HTMLInputElement;
    const qty=view.getByLabelText('수량 (주)') as HTMLInputElement;
    fireEvent.change(price,{target:{value:'70000.50'}});fireEvent.change(qty,{target:{value:'2'}});expect(pending).toHaveLength(1);
    host(false);expect(pending[0].signal.aborted).toBe(true);
    host(true);expect(pending).toHaveLength(2);
    host(true);expect(pending).toHaveLength(2);
    await act(async()=>{pending[0].resolve({...stock,baseDate:'2026-10-27',closePrice:1});pending[1].resolve({...stock,baseDate:'2026-10-27',closePrice:75000});});
    expect(price.value).toBe('70000.50');expect(qty.value).toBe('2');expect(save).not.toHaveBeenCalled();expect(getUsdKrwRate).not.toHaveBeenCalled();
  });
});
