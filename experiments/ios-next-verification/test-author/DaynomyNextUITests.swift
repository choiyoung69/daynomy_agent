import XCTest

/// Run with synthetic fixture on 127.0.0.1:18097. Never injects a logged-in profile.
/// XCUITest is platform evidence only when xcodebuild test actually executes it.
@MainActor final class DaynomyNextUITests: XCTestCase {
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
        app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "삼성전자 · \(side)")).firstMatch
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
    private func holding(_ quantity: Int, average: Int, app: XCUIApplication) {
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
    func testGuestBuyEditSellDeleteReplaysVisibleHoldings() {
        let app = launch()
        XCTAssertTrue(text("게스트 투자 기록", in: app).waitForExistence(timeout: 10))
        openTrade(app, side: "매수", quantity: "10", price: "100"); save(app)
        holding(10, average: 100, app: app)
        let buy = row("매수", in: app); reveal(buy, in: app); buy.tap()
        XCTAssertTrue(app.navigationBars["거래 수정"].waitForExistence(timeout: 5))
        replace(field("tradeQuantity", in: app), with: "12", in: app)
        replace(field("tradeUnitPrice", in: app), with: "110", in: app)
        save(app, editing: true); holding(12, average: 110, app: app)
        openTrade(app, side: "매도", quantity: "2", price: "150"); save(app)
        holding(10, average: 110, app: app)
        // Sale earns (150 - 110) * 2 = 80 KRW, independently of fixture valuation.
        app.swipeDown(); app.swipeDown()
        XCTAssertTrue(text("실현손익, 80 원", in: app).waitForExistence(timeout: 5))
        deleteRow("매도", in: app); holding(12, average: 110, app: app)
        deleteRow("매수", in: app)
        XCTAssertTrue(text("아직 보유 자산이 없어요. 첫 거래를 기록해 보세요.", in: app).waitForExistence(timeout: 10))
        XCTAssertTrue(text("기록한 매수·매도 거래가 없어요.", in: app).exists)
    }
    func testGuestOversellKeepsEditorAndPreviousHolding() {
        let app = launch()
        openTrade(app, side: "매수", quantity: "3", price: "100"); save(app)
        openTrade(app, side: "매도", quantity: "4", price: "150")
        let saveButton = app.buttons["saveTransaction"]; reveal(saveButton, in: app); saveButton.tap()
        let error = text("해당 거래일의 보유 수량보다 많이 매도할 수 없어요. 이후 거래도 확인해 주세요.", in: app)
        XCTAssertTrue(error.waitForExistence(timeout: 5))
        XCTAssertTrue(app.navigationBars["거래 기록"].exists)
        app.buttons["닫기"].tap(); holding(3, average: 100, app: app)
        XCTAssertFalse(row("매도", in: app).exists)
    }
    func testGuestFeedbackSuccessClearsAndFailurePreservesInput() {
        let app = launch("내 정보")
        let input = app.descendants(matching: .any).matching(identifier: "feedbackField").firstMatch
        XCTAssertTrue(input.waitForExistence(timeout: 5))
        let send = app.buttons["의견 보내기"]
        XCTAssertFalse(send.isEnabled)
        input.tap(); input.typeText("UI fixture feedback"); reveal(send, in: app); send.tap()
        let success = text("의견을 보내 주셔서 감사합니다.", in: app)
        XCTAssertTrue(success.waitForExistence(timeout: 10))
        XCTAssertTrue((input.value as? String ?? "").isEmpty || input.value as? String == "의견을 남겨 주세요")
        XCTAssertFalse(send.isEnabled)
        input.tap(); input.typeText("fixture-reject"); reveal(send, in: app); send.tap()
        XCTAssertTrue(text("검증용 피드백 거절", in: app).waitForExistence(timeout: 10))
        XCTAssertEqual(input.value as? String, "fixture-reject")
        XCTAssertTrue(send.isEnabled)
        XCTAssertTrue(app.buttons["Google로 로그인"].exists)
    }
    func testNewsDetailKeywordAnalysisAndBackNavigation() {
        let app = launch("소식")
        let article = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "검증용 시장 이슈")).firstMatch
        XCTAssertTrue(article.waitForExistence(timeout: 10)); article.tap()
        XCTAssertTrue(app.navigationBars["이슈 상세"].waitForExistence(timeout: 5))
        XCTAssertTrue(text("검증용 상세 본문입니다.", in: app).waitForExistence(timeout: 10))
        let keyword = app.buttons["검증 키워드"]; reveal(keyword, in: app); keyword.tap()
        XCTAssertTrue(text("검증용 정의", in: app).waitForExistence(timeout: 5))
        let analysis = text("검증용 위험 요인", in: app); reveal(analysis, in: app)
        XCTAssertTrue(analysis.waitForExistence(timeout: 10))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(app.navigationBars["둘러보기"].waitForExistence(timeout: 5))
        XCTAssertTrue(article.exists)
    }
    func testClearingPendingTradeSearchStopsSpinner() {
        let app = launch()
        let add = app.buttons["addTransaction"]; reveal(add, in: app); add.tap()
        let query = app.textFields["tradeStockQuery"]
        XCTAssertTrue(query.waitForExistence(timeout: 5)); query.tap(); query.typeText("삼성")
        let spinner = app.descendants(matching: .activityIndicator).matching(identifier: "검색 중").firstMatch
        XCTAssertTrue(spinner.waitForExistence(timeout: 2))
        query.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 2))
        expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: spinner)
        waitForExpectations(timeout: 5)
        XCTAssertTrue(query.value as? String == "" || query.value as? String == "종목명 또는 코드")
        XCTAssertFalse(app.buttons["tradeStock_1"].exists)
    }
    func testGuestHoldingRemovalIgnoresClearedAdjustmentFields() {
        let app = launch()
        openTrade(app, side: "매수", quantity: "3", price: "100"); save(app)
        let adjust = app.buttons["보유 수량·원가 조정"]; reveal(adjust, in: app); adjust.tap()
        XCTAssertTrue(app.navigationBars["보유 정보 정정"].waitForExistence(timeout: 5))
        replace(app.textFields["보유 수량"], with: "", in: app)
        replace(app.textFields["평균 매입가 (원화)"], with: "", in: app)
        let remove = app.buttons["현재 보유에서 삭제"]; reveal(remove, in: app); remove.tap()
        let confirm = app.buttons["보유 삭제"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 3)); confirm.tap()
        XCTAssertTrue(app.navigationBars["포트폴리오"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.navigationBars["보유 정보 정정"].exists)
        XCTAssertTrue(text("아직 보유 자산이 없어요. 첫 거래를 기록해 보세요.", in: app).waitForExistence(timeout: 10))
        // Holding removal is not a trade deletion: the original buy must remain.
        XCTAssertTrue(row("매수", in: app).exists)
    }
    func testNewsTextSearchRendersContentArrayAndOpensDetail() {
        let app = launch("소식")
        let query = app.textFields["뉴스 제목·본문 검색"]
        XCTAssertTrue(query.waitForExistence(timeout: 5)); query.tap(); query.typeText("시장\n")
        let article = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "검색 전용 결과")).firstMatch
        XCTAssertTrue(article.waitForExistence(timeout: 10), "/api/search/news content[] must render in news mode")
        article.tap()
        XCTAssertTrue(app.navigationBars["이슈 상세"].waitForExistence(timeout: 5))
        XCTAssertTrue(text("검색 전용 결과", in: app).waitForExistence(timeout: 10))
    }
}
