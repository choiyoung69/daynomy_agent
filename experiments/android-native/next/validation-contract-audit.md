# Independent validation: initial contract audit

- Validator: `/root/android_next_validation`, distinct from test author and implementer.
- Audit start: 2026-10-28 09:10:43 UTC. Initial audit end: 2026-10-28 09:12:03 UTC.
- Tentative slice: public news list/detail and USD/KRW quote. Scope confirmation remains with coordinator.
- Status: **not approved; runtime and implementation validation pending**.
- No web, Gradle, DB, ADB, original service execution, feature/test writes, or previous pilot evidence edits.
- `python3 scripts/check.py preflight`: exit 0, reference snapshot 29/29. This is environment/source preparation only.

## KB read before original source

All paths below are relative to `knowledge/wiki/`.

| Document | Applied validation rule |
| --- | --- |
| `projects/daynomy/news.md` | Published visibility, pagination, ordering, missing detail and image/source preservation. Its feature-contract section is empty, so use pinned source for the exact DTO. |
| `projects/daynomy/stocks-exchange.md` | Preserve quote currency and actual base date; do not report stored quote as live price. Its feature-contract section is also empty. |
| `packages/android-kotlin/types-and-json.md` | Missing/null distinction, numeric ID type/range, unknown fields do not waive required-field validation. |
| `packages/android-kotlin/numbers-and-money.md` | Construct BigDecimal from JSON numeric lexeme, never through Double; preserve API numeric transport. |
| `packages/android-kotlin/dates-and-unicode.md` | Calendar date and Instant are different; no device timezone conversion for quote baseDate. |
| `packages/android-kotlin/async-and-cancellation.md` | Cancellation must reach HTTP; stale success/error/finally cannot replace newer state. |
| `packages/android-kotlin/state-and-navigation.md` | Own screen/request state explicitly; stop/dispose and back invalidate pending requests. |
| `packages/android-kotlin/errors-and-transactions.md` | Preserve HTTP status/business code distinction; release response resources; malformed success is not empty success. |
| `packages/android-kotlin/modules-and-testing.md` | Pure model examples, actual JVM HTTP, APK build and device behavior are separate evidence layers. |

## Independently checked source contract

Source root: `reference/2026-DAYNOMY-dev/`, read-only.

- News controller/service/DTOs: `backend/src/main/java/org/grit/daynomy/news/{controller/NewsController.java,service/NewsService.java,dto/NewsPageResponse.java,dto/NewsListItemResponse.java,dto/NewsDetailResponse.java,dto/NewsSourceResponse.java,dto/ImageSourceResponse.java,domain/Category.java,domain/News.java}`.
- FX controller/service/DTO/errors: corresponding `exchangerate/{controller/ExchangeRateController.java,service/ExchangeRateService.java,dto/ExchangeRateResponse.java,ExchangeRateErrorCode.java}`; provider error status in `external/ExternalErrorCode.java`.
- Web adapters compared: `frontend/src/features/news/newslist/{api,types}.ts`, `news/newsdetail/{api,types}.ts`, and `stocks/api.ts`.
- Current Rust contract checked in `app/src/service_discovery.rs` and `app/src/service_market.rs`.
- Baseline native boundary checked in `clients/android/market-core/src/main/kotlin/org/daynomy/market/{Models,OkHttpTransport,MarketController}.kt`, app ViewModel and Gradle files, plus `spec/android-native/README.md`.

News server accepts request categories REAL_ESTATE/STOCK/ETF only. The web category-label table has ten values and must not become an Android query oracle. Server list defaults are page=1 and size=15, bounds page>=1 and size=1..100; web adapter explicitly requests size=6. List is publishedAt descending then ID descending, PUBLISHED only. Response keys are items/page/size/totalPages/totalElements/hasNext. Empty and out-of-range pages are valid responses, not missing-news errors.

Server detail content is a String; imageUrl is nullable; imageSource is an object containing name/url/author/license/licenseUrl/type, with empty strings and NONE when unset; sources is an array of name/url objects. Web detail adapter also permits content string arrays and missing imageSource/imageUrl, so tests must explicitly distinguish backend DTO from broader frontend compatibility. List publishedAt permits null; News entity column is nullable, while web detail requires String. Ordinary publication sets a timestamp. The new Android spec should state its intended null defense rather than silently claiming universal parity.

FX requires date, uses calendar dates 2000-01-01 through Seoul today, and may fall back to a baseDate earlier than requestedDate (New York yesterday cutoff, up to fourteen-day provider window). DTO contains requestedDate/baseDate/rate/baseCurrency/quoteCurrency, with numeric rate and USD/KRW. Current web adapter only validates and returns baseDate/rate. Preserving all server fields in Android is useful but is an explicit stronger boundary than the old web decoder. Rate must be positive. Server status/code cases include 400 INVALID_EXCHANGE_RATE_DATE, 429 EXCHANGE_RATE_RATE_LIMITED, 503 EXCHANGE_RATE_UNAVAILABLE and 502 EODHD_API_REQUEST_FAILED; Rust without provider configuration also yields 503 EODHD_API_NOT_CONFIGURED.

## Proposed independent validation cases

1. Verify test oracles against those source distinctions before accepting their freeze; record any deliberate Android defensive mapping in the new spec.
2. News list normal/empty/out-of-range pages, each supported category, size endpoints, total metadata, published ordering with ID tie, no DRAFT/REJECTED rows. Use actual Rust/DB synthetic fixtures for server visibility/order, not only decoder mocks.
3. Detail source attribution and imageSource fields survive decoding/rendering; NONE and null imageUrl work; missing ID and unpublished ID stay 404. Unknown fields allowed only while required field checks remain.
4. Strict primitive type rejection, numeric-string IDs rejection, exact safe ID bounds, malformed content/source/image metadata, nullable-vs-missing cases according to explicit spec. Numeric grammar must reject invalid JSON tokens (prior pilot had a regression here).
5. FX exact decimal and exponent lexemes, positive rate, quoted/nonfinite/null/zero/negative rejection, requested/base dates remain distinct, unsupported currency rejection if chosen by spec.
6. Delayed news category/page response cannot overwrite new category/page; delayed detail cannot overwrite a different selected detail or resurrect a closed detail; delayed FX result/error cannot overwrite a new date. Lifecycle stop/close and HTTP cancellation are separate assertions.
7. Public GET calls carry no authentication/CSRF requirements; error, transport, malformed-success and cancellation paths remain distinct. No automatic retry loop for 429/503.
8. Run actual JVM tests plus build/lint and independently review XML test counts/skips. Then actual Rust/DB integration and device navigation/load/error checks under coordinator's exclusive shared slot. Record tested source and APK SHA-256 together and recheck source after execution.

## Open limits

No essential external documentation gap was found. Exact new Android null/missing policy and scope must be fixed by coordinator/test author from the above local evidence. Today-news timezone D03 is relevant only if today endpoint joins scope; it need not block list/detail. Existing baseline documentation and role JSON still describe first pilot scope and cannot stand in for this slice's approval or evidence. No new implementation or frozen test suite existed during this audit, so there is no code approval.

## Coordinator policy received after initial audit

The coordinator fixed scope to public news list/detail and FX and chose original web-guard projection, with explicit Android numeric mapping. This supersedes the tentative stronger decoder proposals above:

- Response NewsCategory allows the web's ten values; request UI filters only ALL/REAL_ESTATE/STOCK/ETF.
- Detail content String is split on newline with empty entries filtered as in web UI; string arrays are preserved. Missing imageSource is allowed, explicit null rejected. publishedAt must be a string, so hypothetical null timestamps from the backend fail format validation.
- FX projection only validates string baseDate and finite positive numeric rate, represented exactly as BigDecimal. requestedDate/currency response fields are not validation requirements. The input date is displayed separately.
- No stronger client date/page/size validation; backend errors propagate. Strict JSON numeric grammar still applies. News IDs use exact signed Long range, without positive/safe-integer enforcement.

These policies have identifiable original web evidence, except exact signed Long is an Android numeric representation choice. Actual Rust responses for normal published rows and FX DTOs fit the projection. Tests should not misdescribe acceptance of extra web categories/content arrays as evidence that the Rust server generates them, or rejection of nullable publishedAt as perfect backend schema parity. The zero/negative ID and large exact integer policy must be tested independently of old stock-ID rules. User-visible request filtering must prevent sending the web's backend-unsupported categories.
