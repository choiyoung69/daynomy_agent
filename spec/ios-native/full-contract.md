# 전체 비리그 iOS 확장 계약

2026-10-28 사용자30분 확장 승인. 기존23개 파일럿 계약/테스트는 보존한다. 이 문서는 실제 앱 전체 완료 보고가 아니다. 테스트 작성→구현→독립검증 순서로 묶음을 전달한다.

## 묶음1: 서비스 transport·경로·네이티브 인증

`ServiceContracts.swift`: public indirect ServiceValue object/array/string/number(String)/bool/null, Equatable/Sendable, object/array/string/number accessors 및 key subscript. ServiceError(status:Int,code:String?,message:String). ServiceEndpoint(path:String,method:String="GET",csrf:Bool=false).

`ServiceClient` actor: init(baseURL:URL,transport:any HTTPTransport); request(path:String,method:String="GET",query:[String:String]=[:],body:ServiceValue?=nil,csrf:Bool=false,retryUnauthorized:Bool=true) async throws ->ServiceValue. 성공204는 null. 숫자 토큰은 Double로 변환하지 않고 보존하며 송신도 숫자로 직렬화한다. 송신의 잘못된 숫자 문법은 네트워크 전에 거절한다. 본문/문자열 escape·query form encoding, HTTP 오류 code/message, 취소, 유효하지 않은 CSRF를 확인한다. Cookie는 URLSessionTransport의 명시적 메모리 session이 관리하고 이 계층은 bearer 토큰을 만들지 않는다.

원본 공통 api/client.ts의 공유 refreshPromise와 CSRF 흐름을 따른다. 401이면 CSRF 조회→POST refresh→원 요청 한 번 재시도; refresh 자체는 재귀 갱신 금지. CSRF headerName/token을 검증해 해당 쓰기 요청에 붙인다. 모바일 exchange만 이 계약상 CSRF 예외이며 게스트 분석은 원본의 별도 흐름을 보존한다. 다른 guest calculate/calendar/feedback·회원/관리자 쓰기는 CSRF를 요구한다. 공통 transport의 DTO 구조 보존은 각 화면의 모든 의미 검증이 완료됐다는 뜻이 아니다.

`ServiceEndpoints.resolve(_ name:String,id:Int64?=nil,secondaryId:Int64?=nil) throws ->ServiceEndpoint`: 정확한 이름/경로/메서드/CSRF 목록은 FullServiceTests.swift의 public/member/admin 표를 따른다. 회원 원장 별칭은 원본 프론트가 실제 쓰는 경로를 사용한다. league/F14 엔드포인트는 없다.

`NativeAuthContract.startURL(baseURL:URL,verifier:String,state:String) throws ->URL`, exchangeBody(callbackURL:URL,expectedState:String,verifier:String) throws ->ServiceValue. [기존 네이티브 인증 계약](../flutter/native-auth.md)이 기준이며 RFC7636 고정 S256 벡터, 정확한 callback scheme/host/path/state, 실패/error/누락 code 거절을 검사한다. verifier/state 생성의 암호학적 난수와 ASWebAuthenticationSession 연결·cookie session은 구현자/기기 검증 대상이다. verifier/code/cookie를 기록하지 않는다.

출처: reference/2026-DAYNOMY-dev/frontend/src/api/client.ts, features/{portfolio,investment-calendar,pages,feedback,search,stock-content,people,admin}/api.ts와 news/{newslist,newsdetail}/api.ts, 기존 KB F01–F13 문서와 service-catalog, app/src/service_auth.rs 및 spec/flutter/native-auth.md. 웹 원본에 없는 모바일 로그인은 승인된 서버 확장 계약이며 웹과 같은 구현으로 주장하지 않는다.

## 실행 경계

canonical Swift Testing 소스는 현재 CLT 런타임 결함 때문에 동일 본문의 독립 standalone harness로 실행한다. experiments/ios-full/test-author/run_host_tests.py는 기존 frozen runner를 복사해 여러 suite가 한 파일에 있을 때 각각 함수 이름을 정확하게 열거하도록 확장했다. 기존23개도 함께 실행하며 각 함수 실행·실패·총수와 nonzero exit를 남긴다. Xcode/iOS SDK 기기 실행과 구분한다. 파일럿 frozen 원본 하네스는 수정하지 않는다.

## 묶음2: 게스트 거래 원장

PortfolioContracts.swift의 LocalTrade(id:Int64,stock:Stock,type:BUY/SELL,date:String,quantity:Int64,unitPrice:String,fee:String="0",tax:String="0",exchangeRate:String?)와 LocalHolding(stock,quantity,averagePurchasePrice:Decimal)을 사용한다. PortfolioEngine init(openingHoldings:[LocalHolding]=[],today:String), public private(set) trades, mutating add/update/remove(id:), throwing holdings()/realizedProfitLoss()가 계약이다.

원본 guestPortfolioLedger.ts의 날짜→historyId 순 재생·매입 수수료/세금 포함 평균 원가·원화2자리 반올림·USD 환율6자리 적용·매도 원가 유지/실현손익 및 transactionForm.ts의 날짜/수량/금액 scale 규칙을 고정한다. 변경·삭제가 이후 매도를 불가능하게 만들면 전체 변경을 거절하고 이전 원장을 보존한다. 구조체 API의 rollback은 native 명시 계약이다. 단가4자리, 비용2자리, 환율6자리와 safe integer 수량을 지키며 Decimal 연산의 overflow/정밀도 손실은 조용히 통과시키지 않는다. 현재 테스트 묶음은 거래 BUY/SELL/add/edit/delete·초기 보유 재생까지며 보유 ADJUSTED/REMOVED와 영구 저장/계정 migration은 별도 구현·검증이 필요하다. UI에서 거래가 아닌 직접 보유 조정 화면을 완료했다고 주장하지 않는다.
