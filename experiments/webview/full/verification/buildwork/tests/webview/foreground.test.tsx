/** @vitest-environment jsdom */
// Implementation-authored lifecycle regression; separate from independent frozen acceptance.
import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PortfolioTransactionEditor } from '../../src/features/portfolio/components/PortfolioTransactionEditor';
import { getLatestStockPrice, searchStocks } from '../../src/features/stocks/api';
vi.mock('../../src/features/stocks/api', () => ({
  getLatestStockPrice: vi.fn(), searchStocks: vi.fn(), getUsdKrwRate: vi.fn(),
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it('pagehide cancels a readonly quote, pageshow resumes while preserving the manual draft', async () => {
  const stock = {assetId:1, assetCode:'005930', name:'삼성전자', category:'STOCK', market:'KOSPI'} as const;
  let firstSignal: AbortSignal | undefined;
  vi.mocked(searchStocks).mockResolvedValue([]);
  vi.mocked(getLatestStockPrice).mockImplementationOnce((_id, signal) => {
    firstSignal = signal;
    return new Promise(() => {});
  }).mockResolvedValue({...stock, baseDate:'2026-10-27', closePrice:75000});
  const save = vi.fn();
  const view=render(<PortfolioTransactionEditor stock={stock} onClose={vi.fn()} onSave={save} />);
  await waitFor(() => expect(getLatestStockPrice).toHaveBeenCalledTimes(1));
  fireEvent.change(view.getByLabelText('거래 단가 (원)'), {target:{value:'81234'}});
  act(() => window.dispatchEvent(new Event('pagehide')));
  expect(firstSignal?.aborted).toBe(true);
  expect(view.getByLabelText('거래 단가 (원)')).toHaveProperty('value','81234');
  act(() => window.dispatchEvent(new Event('pageshow')));
  await waitFor(() => expect(getLatestStockPrice).toHaveBeenCalledTimes(2));
  expect(view.getByLabelText('거래 단가 (원)')).toHaveProperty('value','81234');
  expect(save).not.toHaveBeenCalled();
});
