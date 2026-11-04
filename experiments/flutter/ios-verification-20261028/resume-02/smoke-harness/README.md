# iOS native transport smoke harness

Additional criteria authored separately from the implementer/verifier. Frozen v1,
currency, internal-news and lifecycle tests remain unchanged. Production
`main.dart`, `lib/`, iOS platform and pubspec are not edited. This is not a fake
repository or in-process HTTP fixture: production `main()` creates its normal
native transport and talks to the coordinator-owned Rust/PostgreSQL fixture at
`http://127.0.0.1:18087`.

Only a fresh `.local` shadow receives SDK `integration_test`/`flutter_driver`
dev dependencies and the test target. Its package resolution/plugin registration
therefore includes the instrumentation plugin; describe it separately from the
ordinary production-target simulator build/install/launch evidence.

## Execution by verifier

The test author does not run concurrent Flutter commands or create/operate a
device. Coordinate the Flutter SDK lock and synthetic DB fixture with root first.
Use the verifier's dedicated simulator UDID, not a default/all-device selector.

```sh
python3 experiments/flutter/ios-verification-20261028/resume-02/smoke-harness/prepare_shadow.py --output .local/flutter-ios-smoke-01
cd .local/flutter-ios-smoke-01/app
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer PATH="$PWD/../../../experiments/flutter/ios-verification-20261028/resume-02/toolchain-bin:$PATH" bash ../../../scripts/flutter.sh pub get --offline
DAYNOMY_SMOKE_OUTPUT="$PWD/../results" DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer PATH="$PWD/../../../experiments/flutter/ios-verification-20261028/resume-02/toolchain-bin:$PATH" bash ../../../scripts/flutter.sh drive --device-id YOUR_DEDICATED_UDID --driver test_driver/smoke_driver.dart --target integration_test/live_guest_smoke_test.dart --dart-define=API_BASE_URL=http://127.0.0.1:18087
```

Paths above start at repository root and assume the named fresh shadow. The
process-local `xcrun` wrapper is the independently documented environment fix;
no SDK/pub-cache patch or global developer-directory change is required.

Nine ordered checkpoints cover five tabs, real search/decimal close, relative
internal news/detail/back with form retention, exact guest server evaluation,
holding edit, real news body/keyword/analysis, CPI/missing historical samples,
confirmed holding deletion, and real CSRF feedback success/input clearing.
Screenshots are taken before feedback input is typed and after it clears, never
with the synthetic request body visible. Driver JSON/log output does not include
body/cookies/tokens or screenshot byte arrays. The fixed driver writes PNGs and
checkpoint names only.

The fixture must reserve IDs 910001..910099 and the synthetic current-month CPI
event, as seeded by `flutter_backend_fixture.py`. Assertions are intentionally
specific to the independently established fixture values. A missing checkpoint,
image failure, timeout or mismatched value is a failed run, not a skip. Preserve
the first run and input hashes before making any justified harness correction.
Do not change production behavior or weaken fixture assertions to obtain green.

No real Google login, external URL launch, real AI provider, member CRUD E2E,
physical device, release signing or complete screen-reader audit is covered.
