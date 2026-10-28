# 데이터 경계 재현

Node·macOS Foundation/Swift·Rust의 숫자·JSON·문자열·날짜 차이를 합성 입력으로 관찰한다.
제품 코드·원본·DB·네트워크 서버를 실행하지 않는다. 기대값은 현재 언어 동작의 관찰 기준이며 제품 정책이 아니다.

저장소 루트에서 실행한다. 기존 결과 파일은 덮어쓰지 않는다.

```sh
python3 scripts/knowledge_probes.py --output /tmp/daynomy-language-new-run.json
```

Rust는 저장소의 `.local/cargo` 캐시와 별도 `.local/knowledge-probe-target`을 사용해 offline으로 실행한다.
직접 의존성은 serde_json 1.0.154와 arbitrary_precision 기능이다. 의존성 해석 결과는 Cargo.lock에 있다.
Swift 컴파일 결과와 모듈 캐시는 임시 폴더에 두며, 실행 후 제거한다.

실행 결과에는 버전·명령·종료 코드·관찰값·기대값·입력 파일 해시를 기록한다.
종료 0은 실행 가능한 예제의 관찰값이 일치했다는 뜻이다. 도구 부재는 unavailable로 기록한다.
Kotlin·Dart·Flutter는 이번에 도구 유무만 조사했으며 실행 예제를 구현하지 않았다.
이것은 대상 앱 빌드나 React Native/WebView 런타임·HTTP·DB 검증이 아니다.

[해석과 적용 범위](../../knowledge/wiki/shared/data-semantics.md),
[최초 실행 근거](../../knowledge/evidence/2026-10-28-language-01.json).
