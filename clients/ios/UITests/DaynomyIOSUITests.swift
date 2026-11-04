import XCTest

/// Requires independent fixture server at DAYNOMY_UI_BASE_URL (default localhost:18082).
/// Fixture: q=삼성 -> id 1 삼성전자, 005930, KRW; latest id1 -> price 123.4500,
/// baseDate 2026-10-24. Delay quote at least 2 seconds to exercise edits before response.
/// This target is excluded from SwiftPM and requires Xcode + iOS Simulator.
@MainActor final class DaynomyIOSUITests: XCTestCase {
    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["DAYNOMY_API_BASE_URL"] = ProcessInfo.processInfo.environment["DAYNOMY_UI_BASE_URL"] ?? "http://127.0.0.1:18082"
        app.launch()
        let marketTab = app.tabBars.buttons["종목"]
        if marketTab.waitForExistence(timeout: 5) { marketTab.tap() }
        return app
    }
    private func selectSamsung(_ app: XCUIApplication) {
        let query = app.textFields["stockQuery"]
        XCTAssertTrue(query.waitForExistence(timeout: 5))
        query.tap(); query.typeText("삼성")
        let result = app.buttons["stockResult_1"]
        XCTAssertTrue(result.waitForExistence(timeout: 10))
        result.tap()
    }
    func testSearchSelectionQuoteAndChangeStock() {
        let app = launch()
        selectSamsung(app)
        let price = app.textFields["unitPrice"]
        XCTAssertTrue(price.waitForExistence(timeout: 5))
        let filled = NSPredicate(format: "value == %@", "123.4500")
        expectation(for: filled, evaluatedWith: price)
        waitForExpectations(timeout: 10)
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "2026-10-24")).firstMatch.exists)
        app.buttons["changeStock"].tap()
        XCTAssertTrue(app.textFields["stockQuery"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.textFields["unitPrice"].exists)
    }
    func testManualDeletionRemainsEmptyAfterLateQuote() {
        let app = launch()
        selectSamsung(app)
        let price = app.textFields["unitPrice"]
        XCTAssertTrue(price.waitForExistence(timeout: 5))
        price.tap(); price.typeText("77")
        price.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 2))
        // Wait on quote's visible reference date, rather than sleeping, then check empty dirty value.
        let date = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "2026-10-24")).firstMatch
        XCTAssertTrue(date.waitForExistence(timeout: 10))
        // iOS 27 exposes the placeholder as value for an empty SwiftUI TextField.
        let value = price.value as? String
        let placeholder = price.placeholderValue
        XCTAssertEqual(placeholder, "단가")
        XCTAssertTrue(value == "" || (placeholder == "단가" && value == placeholder), "Manual deletion must remain empty, never 77 or the delayed quote: \(String(describing: value))")
    }
}
