import Foundation

// Foundation on macOS only: this does not validate an iOS application.
struct Identifier: Decodable { let id: Int64 }
struct OptionalCurrency: Decodable { let currency: String? }
struct RequiredCurrency: Decodable { let currency: String }
func bytes(_ string: String) -> Data { Data(string.utf8) }
let decoder = JSONDecoder()
let missing = try decoder.decode(OptionalCurrency.self, from: bytes("{}"))
let explicitNull = try decoder.decode(OptionalCurrency.self, from: bytes("{\"currency\":null}"))
let id = try decoder.decode(Identifier.self, from: bytes("{\"id\":9007199254740993}"))
let decimal = Decimal(string: "0.1")! + Decimal(string: "0.2")!
let output: [String: Any] = [
    "int64IdText": String(id.id),
    "optionalMissingIsNil": missing.currency == nil,
    "optionalNullIsNil": explicitNull.currency == nil,
    "requiredMissingRejected": (try? decoder.decode(RequiredCurrency.self, from: bytes("{}"))) == nil,
    "decimalSum": NSDecimalNumber(decimal: decimal).stringValue,
    "emojiCharacterCount": "😀".count,
    "emojiUtf16Count": "😀".utf16.count,
    "decomposedEqualsComposed": "e\u{301}" == "é"
]
let encoded = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
print(String(decoding: encoded, as: UTF8.self))
