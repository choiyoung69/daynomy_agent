import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:daynomy_flutter/daynomy.dart';
import 'support/fakes.dart';

void main() {
  testWidgets('250ms debounce 전에는 요청 없고 마지막 검색어로 1회 조회', (tester) async {
    final transport=FakeTransport((_)=>ApiResponse(200,stockBody));
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    controller.query('삼');
    await tester.pump(const Duration(milliseconds:200));
    controller.query('삼성');
    await tester.pump(const Duration(milliseconds:249));
    expect(transport.requests,isEmpty);
    await tester.pump(const Duration(milliseconds:1));
    await tester.pump();
    expect(transport.requests.length,1);
    expect(Uri.parse(transport.requests.single.path).queryParameters['q'],'삼성');
    expect(controller.stocks.map((s)=>s.name),['삼성전자','KODEX 200']);
    expect(controller.loading,isFalse);
  });
  testWidgets('빈 검색어는 이전 요청을 취소하고 결과를 비운다', (tester) async {
    final pending=Completer<ApiResponse>();
    final transport=FakeTransport((_)=>pending.future);
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    controller.query('삼성');
    await tester.pump(const Duration(milliseconds:250));
    expect(controller.loading,isTrue);
    controller.query('   ');
    expect(transport.requests.single.cancel?.isCancelled,isTrue);
    pending.complete(ApiResponse(200,stockBody));
    await tester.pump();
    expect(controller.stocks,isEmpty);
    expect(controller.loading,isFalse);
  });
  testWidgets('실제 cancel 전달 + 취소를 무시한 이전 응답도 세대 검사로 무시', (tester) async {
    final first=Completer<ApiResponse>();
    final second=Completer<ApiResponse>();
    var cancelled=false;
    final transport=FakeTransport((request) {
      request.cancel?.onCancel(()=>cancelled=true);
      return Uri.parse(request.path).queryParameters['q']=='old' ? first.future : second.future;
    });
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    controller.query('old');
    await tester.pump(const Duration(milliseconds:250));
    controller.query('new');
    await tester.pump(const Duration(milliseconds:250));
    expect(cancelled,isTrue);
    second.complete(ApiResponse(200,stockBody.replaceAll('삼성전자','최신 검색')));
    await tester.pump();
    first.complete(ApiResponse(200,stockBody.replaceAll('삼성전자','이전 검색')));
    await tester.pump();
    expect(controller.stocks.first.name,'최신 검색');
  });
  testWidgets('국가 변경은 새 요청, ETF 분류는 결과 필터', (tester) async {
    final transport=FakeTransport((_)=>ApiResponse(200,stockBody));
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    controller.query('ETF');
    await tester.pump(const Duration(milliseconds:250));
    await tester.pump();
    controller.updateFilters(country:'US',category:'ETF');
    await tester.pump(const Duration(milliseconds:250));
    await tester.pump();
    expect(Uri.parse(transport.requests.last.path).queryParameters['country'],'US');
    expect(controller.stocks.map((s)=>s.category),['ETF']);
  });
  testWidgets('서버 오류를 error에 남기고 loading 종료', (tester) async {
    final transport=FakeTransport((_)=>ApiResponse(503,'{"code":"TEMPORARY_UNAVAILABLE"}'));
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    controller.query('삼성');
    await tester.pump(const Duration(milliseconds:250));
    await tester.pump();
    expect(controller.error,isA<ApiException>());
    expect(controller.loading,isFalse);
    expect(controller.stocks,isEmpty);
  });
  testWidgets('자동 종가 대기 중 수동으로 편집한 가격을 보존', (tester) async {
    final pending=Completer<ApiResponse>();
    final transport=FakeTransport((_)=>pending.future);
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    final selected=controller.selectStock(decodeStocks(stockBody).first);
    controller.setManualPrice('77777.2500');
    pending.complete(ApiResponse(200,priceBody));
    await selected;
    expect(controller.priceText,'77777.2500');
  });
  testWidgets('선택 종목을 바꾼 뒤 이전 종가 응답이 가격을 덮지 않는다', (tester) async {
    final first=Completer<ApiResponse>();
    final second=Completer<ApiResponse>();
    final transport=FakeTransport((r)=>r.path.contains('/1/') ? first.future : second.future);
    final controller=SearchController(repository(transport));
    addTearDown(controller.dispose);
    final stocks=decodeStocks(stockBody);
    final a=controller.selectStock(stocks.first);
    final b=controller.selectStock(stocks.last);
    second.complete(ApiResponse(200,priceBody.replaceAll('"assetId":1','"assetId":2').replaceAll('71234.1250','99.9000')));
    await b;
    first.complete(ApiResponse(200,priceBody));
    await a;
    expect(controller.priceText,'99.9000');
    expect(transport.requests.first.cancel?.isCancelled,isTrue);
  });
  testWidgets('dispose는 전송을 취소하고 늦은 완료 뒤 notify하지 않는다', (tester) async {
    final pending=Completer<ApiResponse>();
    final transport=FakeTransport((_)=>pending.future);
    final controller=SearchController(repository(transport));
    var notifications=0;
    controller.addListener(()=>notifications++);
    controller.query('삼성');
    await tester.pump(const Duration(milliseconds:250));
    controller.dispose();
    final before=notifications;
    pending.complete(ApiResponse(200,stockBody));
    await tester.pump();
    expect(transport.requests.single.cancel?.isCancelled,isTrue);
    expect(notifications,before);
    expect(tester.takeException(),isNull);
  });
}
