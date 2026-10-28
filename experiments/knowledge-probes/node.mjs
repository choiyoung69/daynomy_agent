// Synthetic boundary examples; this does not run React Native or WebView.
const missing = JSON.parse('{}');
const explicitNull = JSON.parse('{"currency":null}');
const date = new Date('2026-10-28');
const parts = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit'
}).formatToParts(date);
const part = name => parts.find(value => value.type === name).value;
console.log(JSON.stringify({
  unsafeIdText: String(JSON.parse('{"id":9007199254740993}').id),
  unsafeIdAccepted: Number.isSafeInteger(JSON.parse('{"id":9007199254740993}').id),
  binarySum: String(0.1 + 0.2),
  missingOwnKey: Object.hasOwn(missing, 'currency'),
  nullOwnKey: Object.hasOwn(explicitNull, 'currency'),
  omittedUndefined: JSON.stringify({currency: undefined}),
  explicitNull: JSON.stringify({currency: null}),
  dateInLosAngeles: `${part('year')}-${part('month')}-${part('day')}`,
  emojiUtf16Length: '😀'.length,
  decomposedEqualsComposed: 'e\u0301' === 'é'
}));
