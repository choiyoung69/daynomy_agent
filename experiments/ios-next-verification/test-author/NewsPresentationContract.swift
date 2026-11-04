import Foundation

// Compiled together with real DaynomyCore sources by run_presentation_contract.py.
// This executable is separate from the unchanged 51-method host suite.
@main struct NewsPresentationContract {
    static func main() {
        var failures = 0
        func check(_ value: Bool, _ name: String) {
            if !value { failures += 1; print("FAIL \(name)") }
            else { print("PASS \(name)") }
        }
        let searchRow = ServiceValue.object(["id": .number("71"), "title": .string("검색 전용 이슈")])
        let listRow = ServiceValue.object(["id": .number("72"), "title": .string("목록 전용 이슈")])
        let ambiguous = ServiceValue.object(["content": .array([searchRow]), "items": .array([listRow])])
        check(NewsPresentation.items(payload: .object(["content": .array([searchRow])]), isNewsSearch: true) == [searchRow], "search uses content")
        check(NewsPresentation.items(payload: .object(["items": .array([listRow])]), isNewsSearch: false) == [listRow], "regular list uses items")
        check(NewsPresentation.items(payload: ambiguous, isNewsSearch: true) == [searchRow], "search cannot prefer unrelated items")
        check(NewsPresentation.items(payload: ambiguous, isNewsSearch: false) == [listRow], "regular list cannot prefer unrelated content")
        check(NewsPresentation.items(payload: .object(["items": .array([listRow])]), isNewsSearch: true).isEmpty, "wrong search shape does not fallback")
        check(NewsPresentation.items(payload: .object(["content": .array([searchRow])]), isNewsSearch: false).isEmpty, "wrong list shape does not fallback")
        check(NewsPresentation.items(payload: .null, isNewsSearch: true).isEmpty, "null search is empty")
        check(NewsPresentation.items(payload: .object(["content": .string("invalid")]), isNewsSearch: true).isEmpty, "non-array content is empty")
        check(NewsPresentation.adminCategoryCodes == ["STOCK", "ETF", "REAL_ESTATE"], "admin codes exactly match accepted backend enum and order")
        check(!NewsPresentation.adminCategoryCodes.contains("ECONOMY"), "unsupported ECONOMY cannot be authored")
        print("PRESENTATION CONTRACT 10 checks; failures \(failures)")
        exit(failures == 0 ? 0 : 1)
    }
}
