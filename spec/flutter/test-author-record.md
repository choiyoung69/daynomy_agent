# 테스트 작성 역할 기록

- 역할: `/root/flutter_tests`, 2026-10-28 KST. Flutter `lib/`와 Rust 구현을 작성하지 않았다.
- 지시: 지식베이스 기반 전체 사용자 앱, 독립 테스트 → 별도 구현 → 별도 검증 순서.
- 산출: Flutter 테스트 6개 + fake support 1개, 사용자 route 사례 34개, 원본 decoder fixture 21개,
  핵심 guest/server-calculation와 member trade CRUD widget 흐름, native auth와 cookie jar,
  `scripts/flutter_auth_acceptance.py`의 독립 로컬 Google fixture HTTP/DB 인수 검사.
- `python3 -m py_compile scripts/flutter_auth_acceptance.py`: exit 0.
- SDK direct `dart format clients/flutter/test`는 Dart CLI analytics가 쓰기 허용 밖
  `/Users/seoyeong/.dart-tool`에 설정을 생성하려 하여 CLI 초기화에서 실패했다. XDG_CONFIG_HOME을
  local로 바꾼 재시도도 동일했다. 테스트 실패를 수정하려 구현/기준을 바꾸지 않았다.
- 실제 Flutter red 실행과 기준 SHA-256 manifest는 조정자의 `scripts/flutter_check.py --phase red`에서
  기록한다. 앱 export가 없는 import failure는 예상되며, 이것만으로 실제 결함을 검출했다고
  주장하지 않는다. 별도 backend HTTP red로 endpoint 부재도 확인해야 한다.
- 수정 범위: `clients/flutter/test/**`, `spec/flutter/test-contract.md`, 이 기록,
  사용자 추가 승인에 따른 `scripts/flutter_auth_acceptance.py`만 작성했다. reference 읽기 전용.
- 남은 일: 구현 역할이 계약을 구현하고, 다른 검증 역할이 실제 테스트 실행·부정 사례·실서버
  HTTP/DB·플랫폼 빌드 및 남은 한계를 보고해야 한다. 테스트 작성은 앱 완료가 아니다.

기준 fixture 오류를 발견하면 원본 근거를 먼저 남기고 테스트 작성 역할이 정정한다.
구현자가 통과를 위해 테스트를 완화해서는 안 된다.

고정 전 원본 대조 정정: `PortfolioHoldingRequest.java:14`가 평균 매입가를 fraction=2로
제한하므로 guest widget 입력과 기대값을 60000.1000에서 60000.10으로 정정했다.
거래단가는 `PortfolioTransactionRequest.java:17`의 fraction=4에 맞춰 65000.5000을 유지한다.
JSON parser/종가 테스트의 4자리 원문 보존 검사는 유지한다.
