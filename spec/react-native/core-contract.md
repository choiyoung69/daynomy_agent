# React Native core contract — 2026-10-28

Scope: nonleague DAYNOMY client, native View/Text/TextInput UI, shared TypeScript core. Test author, implementation author, independent verification roles are separate. This file is a contract, not native completion evidence.

Sources read: `knowledge/wiki/platforms/react-native.md`, `knowledge/wiki/shared/auth-storage.md`, `knowledge/wiki/porting/stock-search-price.md`, `spec/ios-native/full-contract.md`, original `frontend/src/api/client.ts`, `features/stocks/api.ts`, `features/news/newslist/{api,types}.ts`, `features/portfolio/{transactionForm,guestPortfolioLedger}.ts`.

## Frozen interfaces

`clients/react-native/src/core.ts` exports Stock/Trade/Endpoint/RequestOptions, endpoint(name,id?,secondaryId?), buildURL(base,path,query), ServiceClient(base,transport=fetch).request(path,options), decodeStocks, decodePrice, decodeNewsPage, validateTrade(trade,today), replayLedger(trades), StockSelection. The stub carries full signatures. Node 22 executes the independent `tests/core.test.ts` via `node --experimental-strip-types --test`.

27 tests cover exact public/member/admin paths, safe IDs, query encoding and origin bounds, CSRF bootstrap, credentials include, GET refresh once, failed refresh termination, write no replay, stock/price/news shape and null handling, transaction date/scale/currency rules, cost/fee/realized profit replay and oversell, stale search/selection response, manual price preservation. Price decoder deliberately accepts finite zero matching the source API decoder; auto-fill state accepts only positive prices. News categories follow the original known category enum; null image/publishedAt are valid.

Endpoint names match `ServiceEndpoints.swift` aliases, plus stocks/price added by implementation. Mutating requests bootstrap `/api/auth/csrf` only when options.csrf=true and use the returned validated headerName/token. HTTP 204 maps to null. HTTP non-2xx throws error carrying status when available. Credentials use `include`; cookie behavior on real iOS/Android remains platform verification.

**Explicit mobile transport safety policy:** automatic 401 refresh/replay is restricted to GET; writes surface failure without replay. The web source automatically replays writes once. This difference matches the coordinator's requested native contract and prevents ambiguous duplicate writes. GET refresh uses GET csrf → POST refresh → original GET once. Failed refresh cannot recursively refresh. This is not a claim of unchanged web transport behavior.

Ledger inputs use decimal strings with exact arithmetic recommended (unitPrice ≤4 places, fee/tax ≤2, FX ≤6). Rounded cost/profit outputs have two decimal places. Native Trade.date maps to source tradeDate; Trade.id maps history ordering. No future/invalid calendar dates, fractional/unsafe quantities, missing USD FX, or oversells. Replay sorts date then ID, rejects duplicate IDs, and never mutates input. Persistent storage and opening holdings/holding adjustment are outside these 27 tests and require separate evidence.

## RED and freeze

See `experiments/react-native/test-author/red.log` and `frozen.json`. Initial stub execution exit 1: 27 tests, 21 fail, 6 rejection-only cases pass because all stub functions throw. This is an actual execution; no tests skipped. Test hash is fixed before handing implementation over. Stub hash records the initial empty implementation and is expected to change. Tests may not be weakened to make implementation pass. This Node result is not Android/iOS runtime evidence.
