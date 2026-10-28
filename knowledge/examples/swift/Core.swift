import Foundation

// region json
enum Field: Equatable { case missing, null, value(String) }
struct CurrencyPatch: Decodable {
    let currency: Field
    enum Keys: String, CodingKey { case currency }
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: Keys.self)
        if !container.contains(.currency) { currency = .missing }
        else if try container.decodeNil(forKey: .currency) { currency = .null }
        else { currency = .value(try container.decode(String.self, forKey: .currency)) }
    }
}
struct OptionalCurrency: Decodable { let currency: String? }
struct Money: Decodable { let amount: Decimal }
func decode<T: Decodable>(_ type: T.Type, _ text: String) throws -> T {
    try JSONDecoder().decode(type, from: Data(text.utf8))
}
// endregion json

// region collections
struct Position { var quantity: Int }
final class ReferencePosition { var quantity = 1 }
// endregion collections

// region bridge
func trustedBridgeOrigin(_ originFromHost: String, isMainFrame: Bool) -> Bool {
    isMainFrame && originFromHost == "https://app.example.invalid"
}
// endregion bridge

// region state
actor Gate {
    private var generation = 0
    private var alive = true
    private(set) var result: String?
    func begin() -> Int { generation += 1; return generation }
    func accept(_ token: Int, _ value: String) -> Bool {
        guard alive && token == generation else { return false }
        result = value
        return true
    }
    func dispose() { alive = false; generation += 1 }
}
// endregion state

@main struct Run {
    static func main() async throws {
        var results: [String: Bool] = [:]
        func test(_ name: String, _ value: Bool) { precondition(value, name); results[name] = value }
        test("optional_missing_nil", try decode(OptionalCurrency.self, "{}").currency == nil)
        test("optional_null_nil", try decode(OptionalCurrency.self, "{\"currency\":null}").currency == nil)
        test("patch_missing", try decode(CurrencyPatch.self, "{}").currency == .missing)
        test("patch_null", try decode(CurrencyPatch.self, "{\"currency\":null}").currency == .null)
        test("patch_value", try decode(CurrencyPatch.self, "{\"currency\":\"USD\"}").currency == .value("USD"))
        test("decimal_json_sample", try decode(Money.self, "{\"amount\":0.1}").amount == Decimal(string: "0.1")!)
        var amount = Decimal(string: "1.005")!; var rounded = Decimal()
        NSDecimalRound(&rounded, &amount, 2, .plain)
        test("decimal_round_sample", rounded == Decimal(string: "1.01")!)
        test("utf16_vs_character", "😀".utf16.count == 2 && "😀".count == 1)
        test("canonical_string_equality", "e\u{301}" == "é")
        var valueArray = [Position(quantity: 1)]; let valueCopy = valueArray
        valueArray[0].quantity = 2
        test("struct_array_value_copy", valueCopy[0].quantity == 1)
        let refArray = [ReferencePosition()]; let refCopy = refArray
        refArray[0].quantity = 2
        test("reference_elements_shared", refCopy[0].quantity == 2)
        let gate = Gate(); let a = await gate.begin(); let b = await gate.begin()
        test("newest_result", await gate.accept(b, "B"))
        let oldAccepted = await gate.accept(a, "A"); let current = await gate.result
        test("old_result_ignored", !oldAccepted && current == "B")
        await gate.dispose(); test("disposed_result_ignored", !(await gate.accept(b, "late")))
        // region cancellation
        let work = Task { try await Task.sleep(for: .seconds(600)) }
        work.cancel()
        var cancelled = false
        do { try await work.value } catch is CancellationError { cancelled = true }
        test("sleep_observes_cancellation", cancelled)
        test("bridge_trusted_origin", trustedBridgeOrigin("https://app.example.invalid", isMainFrame: true))
        test("bridge_other_origin_rejected", !trustedBridgeOrigin("https://attacker.example.invalid", isMainFrame: true))
        test("bridge_subframe_rejected", !trustedBridgeOrigin("https://app.example.invalid", isMainFrame: false))
        // endregion cancellation
        let encoded = try JSONSerialization.data(withJSONObject: results, options: [.sortedKeys])
        print(String(decoding: encoded, as: UTF8.self))
    }
}
