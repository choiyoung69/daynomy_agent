import 'dart:convert';

final _numberPattern = RegExp(
  r'^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$',
);

class ExactNumber {
  ExactNumber(this.lexeme) {
    if (!_numberPattern.hasMatch(lexeme) || !double.parse(lexeme).isFinite) {
      throw const FormatException('유한한 JSON 숫자가 필요합니다.');
    }
  }
  final String lexeme;
  @override
  String toString() => lexeme;
}

Object? decodeJsonExact(String source) => _Parser(source).parse();
String encodeJsonExact(Object? value) {
  if (value is ExactNumber) return value.lexeme;
  if (value == null || value is bool || value is String || value is int)
    return jsonEncode(value);
  if (value is List) return '[${value.map(encodeJsonExact).join(',')}]';
  if (value is Map<String, Object?>) {
    return '{${value.entries.map((e) => '${jsonEncode(e.key)}:${encodeJsonExact(e.value)}').join(',')}}';
  }
  throw const FormatException('지원하지 않는 JSON 타입입니다. 금액은 ExactNumber를 사용하세요.');
}

class _Parser {
  _Parser(this.s);
  final String s;
  int i = 0;
  Object? parse() {
    if (s.length > 4 * 1024 * 1024) throw const FormatException('응답이 너무 큽니다.');
    final value = read(0);
    ws();
    if (i != s.length) fail();
    return value;
  }

  Never fail() => throw const FormatException('JSON 응답 형식이 올바르지 않습니다.');
  void ws() {
    while (i < s.length && [32, 9, 10, 13].contains(s.codeUnitAt(i))) {
      i++;
    }
  }

  String string() {
    final start = i++;
    while (i < s.length) {
      final c = s.codeUnitAt(i++);
      if (c == 34) return jsonDecode(s.substring(start, i)) as String;
      if (c == 92) {
        if (i == s.length) fail();
        i++;
      } else if (c < 32) {
        fail();
      }
    }
    return fail();
  }

  Object? read(int depth) {
    if (depth > 100) fail();
    ws();
    if (i >= s.length) fail();
    final c = s[i];
    if (c == '"') return string();
    if (c == '{') {
      i++;
      ws();
      final out = <String, Object?>{};
      if (i < s.length && s[i] == '}') {
        i++;
        return out;
      }
      while (true) {
        ws();
        if (i >= s.length || s[i] != '"') fail();
        final key = string();
        /* injected duplicate key acceptance */
        ws();
        if (i >= s.length || s[i++] != ':') fail();
        out[key] = read(depth + 1);
        ws();
        if (i >= s.length) fail();
        final end = s[i++];
        if (end == '}') return out;
        if (end != ',') fail();
      }
    }
    if (c == '[') {
      i++;
      ws();
      final out = <Object?>[];
      if (i < s.length && s[i] == ']') {
        i++;
        return out;
      }
      while (true) {
        out.add(read(depth + 1));
        ws();
        if (i >= s.length) fail();
        final end = s[i++];
        if (end == ']') return out;
        if (end != ',') fail();
      }
    }
    for (final entry in <String, Object?>{
      'null': null,
      'true': true,
      'false': false,
    }.entries) {
      if (s.startsWith(entry.key, i)) {
        i += entry.key.length;
        return entry.value;
      }
    }
    final start = i;
    while (i < s.length && '-+0123456789.eE'.contains(s[i])) {
      i++;
    }
    if (i == start) fail();
    return ExactNumber(s.substring(start, i));
  }
}

BigInt integerValue(Object? value) {
  if (value is int) return BigInt.from(value);
  if (value is! ExactNumber) throw const FormatException('정수가 필요합니다.');
  var text = value.lexeme.toLowerCase();
  final parts = text.split('e');
  var exponent = parts.length == 2 ? int.tryParse(parts[1]) : 0;
  if (exponent == null || exponent.abs() > 1000)
    throw const FormatException('정수 범위 오류');
  text = parts[0];
  final point = text.indexOf('.');
  if (point >= 0) {
    exponent -= text.length - point - 1;
    text = text.replaceFirst('.', '');
  }
  var result = BigInt.parse(text);
  if (exponent >= 0) {
    result *= BigInt.from(10).pow(exponent);
  } else {
    final divisor = BigInt.from(10).pow(-exponent);
    if (result % divisor != BigInt.zero)
      throw const FormatException('정수가 필요합니다.');
    result ~/= divisor;
  }
  return result;
}

int checkedId(Object? value) {
  final integer = integerValue(value);
  if (integer <= BigInt.zero || integer > BigInt.parse('9007199254740991'))
    throw const FormatException('ID 범위가 올바르지 않습니다.');
  return integer.toInt();
}
