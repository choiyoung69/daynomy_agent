import 'dart:async';
import 'dart:convert';

// region json
int checkedId(Object? value) {
  if (value is! int || value <= 0 || value > 9007199254740991) {
    throw const FormatException('ID_RANGE_OR_TYPE');
  }
  return value;
}
String presence(Map<String, Object?> object, String key) {
  if (!object.containsKey(key)) return 'missing';
  return object[key] == null ? 'null' : 'value';
}
// endregion json

// region money
BigInt minorUnits(String input, int scale) {
  if (scale < 0 || scale > 6 || !RegExp(r'^\d+(\.\d+)?$').hasMatch(input)) {
    throw const FormatException('DECIMAL_SYNTAX');
  }
  final parts = input.split('.');
  final fraction = parts.length == 2 ? parts[1] : '';
  if (fraction.length > scale) throw const FormatException('DECIMAL_SCALE');
  return BigInt.parse(parts[0]) * BigInt.from(10).pow(scale) +
      BigInt.parse(fraction.padRight(scale, '0').isEmpty ? '0' : fraction.padRight(scale, '0'));
}
// endregion money

// region dates
bool validCalendarDate(String text) {
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) return false;
  final date = DateTime.tryParse('${text}T00:00:00Z');
  return date != null && date.toIso8601String().substring(0, 10) == text;
}
// endregion dates

// region state
class Gate {
  int generation = 0;
  bool alive = true;
  String? result;
  int begin() => ++generation;
  bool accept(int token, String value) {
    if (!alive || token != generation) return false;
    result = value;
    return true;
  }
  void dispose() { alive = false; generation++; }
}
// endregion state

Future<void> main() async {
  final results = <String, bool>{};
  void test(String name, bool value) {
    if (!value) throw StateError(name);
    results[name] = value;
  }
  bool rejects(void Function() action) { try { action(); return false; } catch (_) { return true; } }
  final missing = jsonDecode('{}') as Map<String, dynamic>;
  final explicit = jsonDecode('{"currency":null}') as Map<String, dynamic>;
  test('missing_and_null_index_equal', missing['currency'] == explicit['currency']);
  test('missing_presence_distinct', presence(missing, 'currency') == 'missing');
  test('null_presence_distinct', presence(explicit, 'currency') == 'null');
  test('safe_id', checkedId(9007199254740991) == 9007199254740991);
  test('large_id_rejected', rejects(() => checkedId(9007199254740993)));
  test('fraction_id_rejected', rejects(() => checkedId(1.5)));
  test('to_int_would_truncate', 1.5.toInt() == 1);
  test('native_large_int_preserved', (jsonDecode('9007199254740993') as int).toString() == '9007199254740993');
  test('binary_decimal_difference', 0.1 + 0.2 != 0.3);
  test('exact_minor_units', minorUnits('1.20', 2) == BigInt.from(120));
  test('minor_units_large_value', minorUnits('9007199254740993.01', 2).toString() == '900719925474099301');
  test('excess_scale_rejected', rejects(() => minorUnits('1.005', 2)));
  test('invalid_date_normalizes', DateTime.parse('2026-02-30').month == 3);
  test('strict_date_rejects_normalized', !validCalendarDate('2026-02-30'));
  test('leap_date_valid', validCalendarDate('2024-02-29'));
  test('emoji_utf16_two', '😀'.length == 2 && '😀'.runes.length == 1);
  final original = <Map<String, int>>[{'price': 1}];
  final shallow = List<Map<String, int>>.of(original);
  final detached = original.map((entry) => Map<String, int>.of(entry)).toList();
  original[0]['price'] = 2;
  test('list_copy_shares_nested_map', shallow[0]['price'] == 2);
  test('detached_nested_map', detached[0]['price'] == 1);
  final gate = Gate(); final a = gate.begin(); final b = gate.begin();
  test('newest_result', gate.accept(b, 'B'));
  test('old_result_ignored', !gate.accept(a, 'A') && gate.result == 'B');
  gate.dispose(); test('disposed_result_ignored', !gate.accept(b, 'late'));
  // region timeout
  final completion = Completer<void>();
  var completedOriginal = false;
  final originalWork = completion.future.then((_) { completedOriginal = true; });
  var timedOut = false;
  try { await originalWork.timeout(Duration.zero); } on TimeoutException { timedOut = true; }
  completion.complete();
  await originalWork;
  test('timeout_does_not_cancel_original', timedOut && completedOriginal);
  // endregion timeout
  print(jsonEncode(results));
}
