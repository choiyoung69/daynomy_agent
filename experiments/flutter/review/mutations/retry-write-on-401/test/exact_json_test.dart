import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:daynomy_flutter/daynomy.dart';

void main() {
  group('JSON 원문 십진수', () {
    test('double로 손실되는 금액·소수·지수의 lexeme를 재귀 보존한다', () {
      const source = '{"amount":9007199254740993.0100,"nested":[0.1000,-2.50,1.25e-3],"text":"123.40","escaped":"\\\"42\\\""}';
      final value = decodeJsonExact(source) as Map<String, Object?>;
      expect((value['amount'] as ExactNumber).lexeme, '9007199254740993.0100');
      expect((value['nested'] as List).map((e) => (e as ExactNumber).lexeme), ['0.1000', '-2.50', '1.25e-3']);
      expect(value['text'], '123.40');
      expect(value['escaped'], '"42"');
      final encoded = encodeJsonExact(value);
      expect(encoded, contains('9007199254740993.0100'));
      expect(encoded, contains('0.1000'));
      expect(jsonDecode(encoded)['text'], '123.40');
    });
    test('객체 key·unicode·null·boolean을 숫자로 오인하지 않는다', () {
      final value = decodeJsonExact('{"123":{"한글😀":"1e3","a":null,"b":true}}') as Map;
      expect(value['123'], {'한글😀': '1e3', 'a': null, 'b': true});
    });
    for (final invalid in ['{"x":01}', '{"x":NaN}', '{"x":Infinity}', '{"x":1,}', '{"x":1,"x":2}', '[] trailing', '{"x":1e400}']) {
      test('malformed/ambiguous JSON 거절: $invalid', () {
        expect(() => decodeJsonExact(invalid), throwsFormatException);
      });
    }
    for (final invalid in ['NaN', 'Infinity', '1,2', '1}', '01', '', '+1']) {
      test('ExactNumber에 JSON injection 거절: $invalid', () {
        expect(() => ExactNumber(invalid), throwsFormatException);
      });
    }
    test('쓰기도 숫자 JSON을 사용하고 금융값을 문자열로 바꾸지 않는다', () {
      expect(encodeJsonExact({'quantity': 2, 'unitPrice': ExactNumber('123.4500')}), '{"quantity":2,"unitPrice":123.4500}');
    });
  });

  group('ID 안전성', () {
    test('최대 safe integer 허용', () => expect(checkedId(ExactNumber('9007199254740991')), 9007199254740991));
    for (final value in <Object?>[0, -1, 1.5, true, null, '1', ExactNumber('9007199254740993'), ExactNumber('1.25')]) {
      test('범위/타입 거절: $value', () => expect(() => checkedId(value), throwsFormatException));
    }
  });

  group('knowledge 고정 원본 decoder fixture', () {
    final source = File('../../knowledge/contracts/stock-search-price.json');
    final contract = jsonDecode(source.readAsStringSync()) as Map;
    for (final item in contract['cases'] as List) {
      test('${item['id']}: ${item['reason']}', () {
        final body = item['body'] as String;
        Object decode() => item['kind'] == 'price' ? decodePrice(body) : decodeStocks(body);
        if (item['expected_accept'] == true) {
          expect(decode, returnsNormally);
        } else {
          expect(decode, throwsFormatException);
        }
      });
    }
    test('종가의 날짜 문자열·소수 원문·통화 fallback', () {
      final quote = decodePrice('{"assetId":1,"assetCode":"AAPL.US","name":"Apple","baseDate":"2026-02-30","closePrice":123.4500}');
      expect(quote.baseDate, '2026-02-30');
      expect(quote.closePrice.lexeme, '123.4500');
      expect(quote.currency, 'USD');
    });
  });
}
