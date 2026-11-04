# ActivityIndicator와 실현손익 AX query 개정

root의 다음 표준폰 재실행 6개는 기존 UI3과 oversell을 합친 4개 통과·2개 실패다. 첫 개정의 빈 단가와 Picker 조회는 실제 UI에서 통과했다. 남은 spinner와 매수/수정/매도/삭제 검사는 아래 실제 계층·녹화 근거를 조사한 뒤 query만 개정했다. 검색 지연은 3초 그대로이며 늘리지 않았다. 앱은 수정하지 않았다.

## 검색 중 표시

`.local/revised-ui-attachments/0242583C-AAA3-4FE2-9CE5-A2CEAB74308A.txt`의 line221은 `ActivityIndicator`, label `검색 중`, value `1`이다. line223에는 별도 StaticText `검색 중`도 있다. 기존 `app.progressIndicators["검색 중"]`는 다른 element type을 조회했다. `activity-indicator-accessibility-excerpt.txt`에 실제 구간을 보존했다.

녹화 `3A474749-D0CA-459D-8D4C-99AB9762353E.mp4`의 13초 프레임 `pending-search-at-query-failure.png`를 직접 확인했다. 입력 `삼성` 아래 실제 spinner와 `검색 중`이 표시되어 있다. 서버 지연이 반영되지 않았다거나 앱이 spinner를 표시하지 않았다는 주장은 이 증거와 맞지 않는다. 최초 fixture의 지연 전제 보완과 이 element-type 오류를 구분한다.

새 query는 `.activityIndicator` 중 label/identifier가 정확히 `검색 중`인 element다. 존재 확인→검색어 두 글자 삭제→같은 indicator의 부재 확인→빈 입력과 이전 선택결과 부재라는 원래 인수 순서는 유지했다.

## 실현손익 80원

`.local/revised-ui-attachments/E8DEB146-0694-4FF1-BEC1-9FACFD9CE178.txt`의 line76은 StaticText label `실현손익, 80 원`이다. 별도 `80 원` StaticText는 없다. 같은 계층 line93에는 `10 주 · 평균 매입가 110 원`이 있다. `realized-profit-accessibility-excerpt.txt`에 손익 구간을 보존했다.

녹화 `B6AF9621-ED86-4CB5-A38A-ED01409216AD.mp4`의 끝 0.5초 전 프레임 `realized-profit-at-query-failure.png`를 직접 확인했다. 실현손익80원과 보유10주·평균110원이 화면에 표시된다. 따라서 이 실패는 손익 산술이나 원장 실패의 증거가 아니다.

손익 query만 정확한 `실현손익, 80 원`으로 변경했다. `(150 - 110) * 2 == 80` 기대값과 이후 매도/매수 삭제·빈 보유/빈 거래 인수는 유지했다.

## 보존과 검사

직전 Picker 개정 버전 전체는 `DaynomyNextUITests.picker-revision.swift`, 이번 두 줄 diff는 `activity-profit-query-revision.diff`다. 원본·AX·두 프레임·diff·현재 Next 소스의 SHA256은 `activity-profit-revision.sha256`에 고정했다. 이전 `picker-revision.sha256`은 당시 stage 해시이며 현재 Next 경로는 후속 개정으로 변경됐다. 최초 원문 사본도 계속 보존한다.

Xcode Swift frontend parse는 통과했다. 새 UI 실행은 root가 실패 관련2개만 수행한다. 이 문서만으로 재실행 성공을 주장하지 않는다. 원시 log/xcresult/전체 hierarchy는 `.local`에 보존하며 공개 artifact에는 개인 절대경로를 복제하지 않았다.
