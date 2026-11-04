# Pending 검색 검사의 fixture 보완

root의 첫 표준폰 NextUI 실행에서 `testClearingPendingTradeSearchStopsSpinner`가 spinner 존재 대기에서 실패했다. 기존 fixture는 `/api/stocks`를 즉시 반환하고 종가 요청만 2.5초 지연한다. 따라서 느린 검색 중 입력 삭제라는 검사의 전제가 서버 응답 시점과 맞지 않았다. 이 실패를 앱 spinner 종료 결함의 재현으로 세지 않는다.

기존 `experiments/ios-next-verification/test-author/ui_fixture.py`와 Next 검사 파일은 보존했다. 이 시점 원본 해시는 `next-original.sha256`이며 Next 원문 사본은 `DaynomyNextUITests.original.swift`다.

새 additive `experiments/ios-sdk-verification/ui_fixture.py`는 기존 Handler를 상속하고 `/api/stocks` GET에만 제어 가능한 지연을 둔 다음 `super().do_GET()`을 호출한다. 기본 지연은 3초이며 다른 응답·CSRF·피드백 검증·종가 지연은 원본 구현을 그대로 사용한다. 포트는 loopback으로만 바인딩한다.

```sh
python3 experiments/ios-sdk-verification/ui_fixture.py --port 18097 --stock-delay 3
python3 experiments/ios-sdk-verification/test-author/check_delayed_fixture.py
```

독립 ephemeral loopback 포트의 smoke는 실제 기본 지연 2.9초 이상, 원본 stock/news/auth/CSRF/feedback/calculate 응답을 확인했다. 결과는 `../delayed-fixture-smoke.log`다. 이 역할은 현재 18097 서버와 Simulator를 제어하지 않았다. root가 서버 교체 후 실패 관련 UI를 재실행하며 UI 통과 여부는 해당 실행에서 판단한다.
