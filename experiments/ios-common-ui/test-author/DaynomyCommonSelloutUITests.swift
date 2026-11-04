import XCTest

/// Run with synthetic fixture on 127.0.0.1:18097. Never injects a logged-in profile.
/// XCUITest is platform evidence only when xcodebuild test actually executes it.
@MainActor final class DaynomyCommonSelloutUITests: XCTestCase {
    private func launch(_ tab: String = "포트폴리오") -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchEnvironment["DAYNOMY_API_BASE_URL"] = ProcessInfo.processInfo.environment["DAYNOMY_UI_BASE_URL"] ?? "http://127.0.0.1:18097"
        app.launch()
        let button = app.tabBars.buttons[tab]
        XCTAssertTrue(button.waitForExistence(timeout: 10)); button.tap()
        return app
    }
    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<7 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.exists && element.isHittable, "Control must be reachable without hiding behind the keyboard")
    }
    private func field(_ id: String, in app: XCUIApplication) -> XCUIElement {
        let direct = app.textFields[id]
        if direct.exists { return direct }
        let container = app.descendants(matching: .any).matching(identifier: id).firstMatch
        return container.descendants(matching: .textField).firstMatch
    }
    private func replace(_ element: XCUIElement, with value: String, in app: XCUIApplication) {
        reveal(element, in: app); element.tap()
        let old = element.value as? String ?? ""
        element.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count + 2))
        element.typeText(value)
    }
    private func text(_ value: String, in app: XCUIApplication) -> XCUIElement {
        app.staticTexts[value]
    }
    private func row(_ side: String, in app: XCUIApplication) -> XCUIElement {
        selectLedger("거래 내역", app: app)
        return app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "삼성전자 · \(side)")).firstMatch
    }
    private func openTrade(_ app: XCUIApplication, side: String, quantity: String, price: String) {
        let add = app.buttons["addTransaction"]; reveal(add, in: app); add.tap()
        let query = app.textFields["tradeStockQuery"]
        XCTAssertTrue(query.waitForExistence(timeout: 5)); query.tap(); query.typeText("삼성")
        let stock = app.buttons["tradeStock_1"]
        XCTAssertTrue(stock.waitForExistence(timeout: 10)); stock.tap()
        let quote = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "2026-10-24 종가 기준")).firstMatch
        XCTAssertTrue(quote.waitForExistence(timeout: 10))
        if side == "매도" {
            // SwiftUI exposes the current value in the iOS 27 picker button label.
            let picker = app.buttons.matching(NSPredicate(format: "label == %@ OR label == %@", "유형", "유형, 매수")).firstMatch
            reveal(picker, in: app); picker.tap(); app.buttons["매도"].tap()
        }
        replace(field("tradeQuantity", in: app), with: quantity, in: app)
        replace(field("tradeUnitPrice", in: app), with: price, in: app)
    }
    private func save(_ app: XCUIApplication, editing: Bool = false) {
        let save = app.buttons["saveTransaction"]; reveal(save, in: app); save.tap()
        XCTAssertTrue(app.navigationBars["포트폴리오"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.navigationBars[editing ? "거래 수정" : "거래 기록"].exists)
        XCTAssertFalse(app.staticTexts["portfolioError"].exists)
    }
    private func selectLedger(_ name: String, app: XCUIApplication) {
        let segment = app.segmentedControls["portfolioLedgerPicker"].buttons[name]
        reveal(segment, in: app); segment.tap()
    }
    private func holding(_ quantity: Int, average: Int, app: XCUIApplication) {
        selectLedger("보유 자산", app: app)
        let label = text("\(quantity) 주 · 평균 매입가 \(average) 원", in: app)
        reveal(label, in: app); XCTAssertTrue(label.waitForExistence(timeout: 10))
    }
    private func deleteRow(_ side: String, in app: XCUIApplication) {
        let trade = row(side, in: app)
        // A partially obscured row may be hittable while its swipe center is behind the tab bar.
        let top = app.navigationBars.firstMatch.frame.maxY + 8
        let bottom = app.tabBars.firstMatch.frame.minY - 12
        func unobscured() -> Bool {
            trade.exists && trade.isHittable && trade.frame.minY >= top && trade.frame.maxY <= bottom
        }
        for _ in 0..<7 {
            if unobscured() { break }
            if trade.exists && trade.frame.minY < top { app.swipeDown() }
            else { app.swipeUp() }
        }
        XCTAssertTrue(unobscured(), "Entire transaction row must be above the tab bar before swiping")
        let start = trade.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5))
        let end = trade.coordinate(withNormalizedOffset: CGVector(dx: 0.45, dy: 0.5))
        start.press(forDuration: 0.05, thenDragTo: end)
        let remove = app.buttons["삭제"]
        XCTAssertTrue(remove.waitForExistence(timeout: 3)); remove.tap()
        let confirm = app.buttons["거래 삭제"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 3)); confirm.tap()
        expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: trade)
        waitForExpectations(timeout: 10)
    }
    func testFullSelloutRetainsCumulativeRealizedProfitAndLedger() {
        let app = launch()
        openTrade(app, side: "매수", quantity: "2", price: "110"); save(app)
        holding(2, average: 110, app: app)
        openTrade(app, side: "매도", quantity: "2", price: "150"); save(app)
        selectLedger("보유 자산", app: app)
        app.swipeDown(); app.swipeDown()
        // Service F05 + original PortfolioLedgerCalculator: (150 - 110) * 2 = 80,
        // even when zero quantity removes the final holding from positions.
        XCTAssertTrue(text("실현손익, 80 원", in: app).waitForExistence(timeout: 10))
        XCTAssertTrue(text("현재 보유 자산이 없어요", in: app).exists)
        XCTAssertFalse(text("아직 보유 자산이 없어요. 첫 거래를 기록해 보세요.", in: app).exists)
        let buy = row("매수", in: app); reveal(buy, in: app); XCTAssertTrue(buy.exists)
        let sell = row("매도", in: app); reveal(sell, in: app); XCTAssertTrue(sell.exists)
    }
}
