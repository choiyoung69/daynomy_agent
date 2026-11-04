# Knowledge coverage 회귀 테스트 fixture 수정

- 역할: 테스트 작성. 변경 범위는 `scripts/test_knowledge.py`의 `test_missing_service_context_fails_coverage` 한 메서드뿐이다. 기존 파일의 다른 미커밋 변경은 보존했다.
- 원본 실패 재현: `python3 -m unittest discover -s scripts -p test_knowledge.py`, 19개 실행, 1개 실패, 종료 코드 1 (`before.log`, `before.exit`). 기대한 `feature has no context mapping: account` 대신 `android: invalid approved feature scope`에서 실패했다.
- 원인: 이 테스트는 복제한 합성 fixture에서 `features.account`만 삭제했다. 현재 실제 Android와 WebView의 `approved_features`가 `account`를 참조하므로, `coverage()`가 서비스 매핑을 검사하기 전에 `load_packs()`의 올바른 참조 무결성 검사에 걸렸다.
- 수정: 합성 fixture에서만 명시된 플랫폼 승인 범위를 존재하는 별도 기능 `stock-search-price`로 고정한 뒤 `account` 매핑을 제거한다. 따라서 플랫폼 참조는 유효하며 원래 의도인 서비스 매핑 누락 오류를 직접 검사한다. 서비스 coverage의 종료 코드 1 및 정확한 오류 문자열 assertion은 유지했다. 실제 `knowledge.py`, `packs.json`과 검사를 변경하지 않았다.
- 수정 후: 같은 명령으로 19개 실행, 모두 성공, 종료 코드 0 (`after.log`, `after.exit`). DB, 다른 테스트 및 구현 파일은 변경하지 않았다.

`evidence.json`은 실행 명령, 종료 코드 및 이 변경과 관련된 현재 파일 해시를 기록한다. 전체 파일 해시는 공유 작업 디렉터리의 해당 시점 스냅샷이며 다른 역할의 기존 변경까지 본 역할이 작성했다는 뜻이 아니다.
