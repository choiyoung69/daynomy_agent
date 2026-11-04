import 'dart:async';
import 'package:daynomy_flutter/daynomy.dart';

typedef Handler = FutureOr<ApiResponse> Function(ApiRequest request);

class FakeTransport implements ApiTransport {
  FakeTransport(this.handler);
  final Handler handler;
  final requests = <ApiRequest>[];
  @override
  Future<ApiResponse> send(ApiRequest request) async {
    requests.add(request);
    return handler(request);
  }
}

const csrfBody = '{"headerName":"X-XSRF-TOKEN","token":"test-only-token"}';
const stockBody = '{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI"},{"assetId":2,"assetCode":"069500","name":"KODEX 200","category":"ETF","market":"KOSPI"}]}';
const priceBody = '{"assetId":1,"assetCode":"005930","name":"삼성전자","baseDate":"2026-10-28","closePrice":71234.1250,"currency":"KRW"}';
const holdingBody = '{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","quantity":2,"averagePurchasePrice":60000.10}';
const profileBody = '{"id":7,"email":"test@example.invalid","name":null,"nickname":"투자일기","role":"USER"}';
const savedPortfolioBody = '{"holdings":[$holdingBody],"totalRealizedProfitLoss":12.3450}';
const transactionBody = '{"transactionId":11,"holding":$holdingBody,"totalRealizedProfitLoss":12.3450}';
const newsPageBody = '{"items":[{"id":3,"title":"기준금리와 시장","category":"ECONOMY","imageUrl":null,"publishedAt":"2026-10-28T09:00:00+09:00"}],"page":1,"size":6,"totalPages":1,"totalElements":1,"hasNext":false}';
const newsDetailBody = '{"id":3,"title":"기준금리와 시장","category":"ECONOMY","publishedAt":"2026-10-28T09:00:00+09:00","content":["금리 흐름을 확인합니다.","출처를 확인하세요."],"sources":[{"name":"한국은행","url":"https://www.bok.or.kr"}]}';
const calendarBody = '{"year":2026,"month":10,"events":[]}';
const emptyAnalysisBody = '{"totalAssetCount":0,"analyzedAssetCount":0,"overallDirection":null,"overallScore":null,"positiveImpactScore":0,"negativeImpactScore":0,"analyzedAt":null,"overallImpact":"근거 부족","impacts":[],"sources":[],"coverage":"INSUFFICIENT"}';
const savedAnalysisBody = '{"status":"EMPTY","lastCheckOutcome":null,"analysisId":null,"matchesCurrentPortfolio":false,"lastSucceededAt":null,"lastFailedAt":null,"failureCode":null,"changeReason":null,"analysis":null}';
const calculationBody = '{"baseDate":null,"pricingStatus":"PARTIAL","pricedHoldingCount":0,"unpricedHoldingCount":0,"totalPurchaseAmount":0,"totalEvaluationAmount":0,"dailyProfitLoss":null,"dailyReturnRate":null,"totalProfitLoss":null,"totalReturnRate":null,"holdings":[],"marketAllocations":[]}';
const performanceBody = '{"status":"INSUFFICIENT_DATA","reason":"SNAPSHOT_DATA_INSUFFICIENT","baseDate":null,"previousBaseDate":null,"points":[],"currentPoint":null}';
const contentsBody = '{"items":[],"page":1,"size":12,"totalPages":0,"totalElements":0,"hasNext":false}';

AppRepository repository(FakeTransport transport) => AppRepository(ApiClient(transport: transport));

/// Tests route the app through the real repository/client, never a mock UI model.
ApiResponse defaultResponse(ApiRequest request, {bool member = false}) {
  final uri = Uri.parse(request.path);
  if (uri.path == '/api/auth/csrf') return ApiResponse(200, csrfBody);
  if (uri.path == '/api/auth/refresh') return ApiResponse(401, '{"code":"UNAUTHORIZED","message":"로그인이 필요합니다."}');
  if (uri.path == '/api/users/me') return member ? ApiResponse(200, profileBody) : ApiResponse(401, '{"code":"UNAUTHORIZED","message":"로그인이 필요합니다."}');
  if (uri.path == '/api/stocks') return ApiResponse(200, stockBody);
  if (uri.path == '/api/stocks/1/price') return ApiResponse(200, priceBody);
  if (uri.path == '/api/portfolio/calculate') return ApiResponse(200, calculationBody);
  if (uri.path == '/api/portfolio/analysis') return ApiResponse(200, emptyAnalysisBody);
  if (uri.path == '/api/news') return ApiResponse(200, newsPageBody);
  if (uri.path == '/api/news/3') return ApiResponse(200, newsDetailBody);
  if (uri.path.endsWith('/keywords')) return ApiResponse(200, '{"keywords":[]}');
  if (uri.path.endsWith('/market-analysis')) return ApiResponse(404, '{"code":"NOT_FOUND"}');
  if (uri.path == '/api/people') return ApiResponse(200, '{"people":[]}');
  if (uri.path == '/api/contents' || uri.path == '/api/search/contents') return ApiResponse(200, contentsBody);
  if (uri.path.contains('investment-calendar')) return ApiResponse(200, calendarBody);
  if (uri.path == '/api/feedback') return ApiResponse(204, '');
  if (uri.path == '/api/users/me/portfolio') return ApiResponse(200, savedPortfolioBody);
  if (uri.path.contains('/performance')) return ApiResponse(200, performanceBody);
  if (uri.path.endsWith('/histories') || uri.path.endsWith('/analysis/history')) return ApiResponse(200, '[]');
  if (uri.path.contains('/portfolio/analysis')) return ApiResponse(200, savedAnalysisBody);
  return ApiResponse(404, '{"code":"NOT_FOUND","message":"테스트에 등록되지 않은 경로"}');
}
