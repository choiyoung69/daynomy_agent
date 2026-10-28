// Executed after Node's type stripping; this does not render React Native or WebView.
export {};
const checks: Record<string, boolean> = {};
function test(name: string, condition: boolean): void {
  if (!condition) throw new Error(name);
  checks[name] = condition;
}
// region json
function checkedId(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('ID_RANGE_OR_TYPE');
  }
  return value;
}
function fieldPresence(object: Record<string, unknown>, key: string): 'missing' | 'null' | 'value' {
  return !Object.hasOwn(object, key) ? 'missing' : object[key] === null ? 'null' : 'value';
}
// endregion json
// region state
class Gate {
  generation = 0;
  alive = true;
  result: string | undefined;
  begin() { return ++this.generation; }
  accept(token: number, value: string) {
    if (!this.alive || token !== this.generation) return false;
    this.result = value;
    return true;
  }
  dispose() { this.alive = false; this.generation++; }
}
// endregion state
// region bridge
type Envelope = { v: 1; id: string; method: 'close'; payload: Record<string, never> };
function decodeBridge(value: unknown): Envelope {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('MESSAGE_TYPE');
  const input = value as Record<string, unknown>;
  if (input.v !== 1 || typeof input.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(input.id) || input.method !== 'close') {
    throw new Error('MESSAGE_SCHEMA');
  }
  if (!input.payload || typeof input.payload !== 'object' || Array.isArray(input.payload) || Object.keys(input.payload).length !== 0) {
    throw new Error('PAYLOAD_SCHEMA');
  }
  return { v: 1, id: input.id, method: 'close', payload: {} };
}
// endregion bridge
function rejects(action: () => unknown) { try { action(); return false; } catch { return true; } }
test('safe_id', checkedId(9007199254740991) === 9007199254740991);
test('rounded_large_id_rejected', rejects(() => checkedId(JSON.parse('9007199254740993'))));
test('quoted_id_rejected', rejects(() => checkedId('1')));
test('missing_distinct', fieldPresence({}, 'currency') === 'missing');
test('null_distinct', fieldPresence({ currency: null }, 'currency') === 'null');
test('undefined_omitted', JSON.stringify({ currency: undefined }) === '{}');
test('binary_money_difference', 0.1 + 0.2 !== 0.3);
test('utf16_length', '😀'.length === 2 && Array.from('😀').length === 1);
test('raw_unicode_not_equal', String('e\u0301') !== String('é'));
// region collections
const mutable = [1]; const readOnly: readonly number[] = mutable; mutable.push(2);
test('readonly_is_alias', readOnly.length === 2);
const source = { rows: [{ quantity: 1 }] }; const copy = { ...source };
source.rows[0].quantity = 2;
test('spread_is_shallow', copy.rows[0].quantity === 2);
// endregion collections
const gate = new Gate(); const a = gate.begin(); const b = gate.begin();
test('newest_result', gate.accept(b, 'B'));
test('old_result_ignored', !gate.accept(a, 'A') && gate.result === 'B');
gate.dispose(); test('disposed_result_ignored', !gate.accept(b, 'late'));
// region cancellation
const controller = new AbortController(); let adapterCancelled = false;
controller.signal.addEventListener('abort', () => { adapterCancelled = true; }, { once: true });
controller.abort();
test('abort_adapter_wiring', controller.signal.aborted && adapterCancelled);
let complete!: () => void; let originalCompleted = false;
const original = new Promise<void>(resolve => { complete = resolve; }).then(() => { originalCompleted = true; });
await Promise.race([original, Promise.resolve('timeout')]);
complete(); await original;
test('race_does_not_cancel_original', originalCompleted);
// endregion cancellation
test('bridge_close_accepted', decodeBridge({ v: 1, id: 'req_1', method: 'close', payload: {} }).method === 'close');
test('bridge_unknown_method_rejected', rejects(() => decodeBridge({ v: 1, id: 'x', method: 'eval', payload: {} })));
test('bridge_version_rejected', rejects(() => decodeBridge({ v: 2, id: 'x', method: 'close', payload: {} })));
test('bridge_payload_rejected', rejects(() => decodeBridge({ v: 1, id: 'x', method: 'close', payload: { code: 'x' } })));
console.log(JSON.stringify(checks));
