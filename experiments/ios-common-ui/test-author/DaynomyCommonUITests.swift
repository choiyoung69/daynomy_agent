import XCTest

/// Additive revision of navigation acceptance, common-uiux sections 2, 11–12.
/// Synthetic loopback evidence only. Existing UI suites remain frozen.
@MainActor final class DaynomyCommonUITests: XCTestCase {
    private func launch() -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchEnvironment["DAYNOMY_API_BASE_URL"] = ProcessInfo.processInfo.environment["DAYNOMY_UI_BASE_URL"] ?? "http://127.0.0.1:18097"
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["포트폴리오"].waitForExistence(timeout: 10))
        return app
    }
    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<7 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.exists && element.isHittable)
    }
    private func issue(_ app: XCUIApplication) {
        app.tabBars.buttons["이슈"].tap()
        XCTAssertTrue(app.buttons["todayNewsNext"].waitForExistence(timeout: 10))
    }
    private func position(_ value: String, app: XCUIApplication) {
        let label = app.staticTexts["todayNewsPosition"]
        XCTAssertTrue(label.waitForExistence(timeout: 10))
        XCTAssertEqual(label.label, value)
    }
    func testThreeDestinationsAndContextualStockLookup() {
        let app = launch()
        XCTAssertEqual(app.tabBars.buttons.count, 3)
        for name in ["포트폴리오", "이슈", "내 계정"] { XCTAssertTrue(app.tabBars.buttons[name].exists) }
        XCTAssertFalse(app.tabBars.buttons["종목"].exists)
        XCTAssertFalse(app.textFields["stockQuery"].exists)
        let market = app.buttons["portfolioMarket"]
        reveal(market, in: app); market.tap()
        let query = app.textFields["stockQuery"]
        XCTAssertTrue(query.waitForExistence(timeout: 5))
        query.tap(); query.typeText("삼성")
        XCTAssertTrue(app.buttons["stockResult_1"].waitForExistence(timeout: 10))
    }
    func testTodayCarouselIsCappedAndPreservesSelectedArticleAfterDetail() {
        let app = launch(); issue(app)
        position("1 / 9", app: app)
        let previous = app.buttons["todayNewsPrevious"]
        let next = app.buttons["todayNewsNext"]
        for control in [previous, next] {
            XCTAssertGreaterThanOrEqual(control.frame.width, 44)
            XCTAssertGreaterThanOrEqual(control.frame.height, 44)
        }
        XCTAssertFalse(previous.isEnabled)
        next.tap(); position("2 / 9", app: app)
        app.buttons["todayNewsArticle_172"].tap()
        XCTAssertTrue(app.staticTexts["검증용 상세 본문입니다."].waitForExistence(timeout: 10))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        position("2 / 9", app: app)
        for _ in 0..<7 { next.tap() }
        position("9 / 9", app: app)
        XCTAssertFalse(next.isEnabled)
        XCTAssertFalse(app.buttons["todayNewsArticle_180"].exists)
        previous.tap(); position("8 / 9", app: app)
    }
    func testNewsSearchRequiresKeyboardSubmissionAndDoesNotReplaceToday() {
        let app = launch(); issue(app)
        app.buttons["todayNewsNext"].tap()
        let query = app.textFields["newsQuery"]
        reveal(query, in: app); query.tap(); query.typeText("시장")
        // A result must not be published by typing alone, even after the old debounce window.
        let result = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "검색 전용 결과")).firstMatch
        let premature = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == true"), object: result)
        premature.isInverted = true
        XCTAssertEqual(XCTWaiter.wait(for: [premature], timeout: 1), .completed)
        XCTAssertFalse(app.scrollViews.buttons["검색"].exists, "Issue content has no separate submit button; the system keyboard Search key is allowed")
        query.typeText("\n")
        XCTAssertTrue(result.waitForExistence(timeout: 10), "Search must render content[] from /api/search/news")
        app.swipeDown(); position("2 / 9", app: app)
        let clear = app.buttons["clearNewsSearch"]
        reveal(clear, in: app); clear.tap()
        XCTAssertFalse(result.exists)
        app.swipeDown(); position("2 / 9", app: app)
    }
    func testSearchFailureLeavesTodayCarouselAvailable() {
        let app = launch(); issue(app)
        app.buttons["todayNewsNext"].tap()
        let query = app.textFields["newsQuery"]
        reveal(query, in: app); query.tap(); query.typeText("실패\n")
        // Failure recovery is the contract; server wording is not product copy.
        XCTAssertTrue(app.staticTexts["newsSearchError"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["다시 시도"].exists)
        XCTAssertFalse(app.staticTexts["검색 결과가 없어요."].exists)
        app.swipeDown(); app.swipeDown()
        position("2 / 9", app: app)
        app.buttons["todayNewsNext"].tap(); position("3 / 9", app: app)
    }
    func testPortfolioHasNoAnalysisOrCalendarShortcut() {
        let app = launch()
        XCTAssertFalse(app.buttons["portfolioAnalysis"].exists)
        XCTAssertFalse(app.buttons["AI 포트폴리오 분석"].exists)
        XCTAssertFalse(app.buttons["투자 캘린더"].exists)
        XCTAssertTrue(app.buttons["addTransaction"].exists)
        XCTAssertTrue(app.buttons["portfolioMarket"].exists)
    }
    func testMarketDepthsHaveBackNavigation() {
        let app = launch()
        app.buttons["portfolioMarket"].tap()
        let marketBar = app.navigationBars["종목과 단가"]
        XCTAssertTrue(marketBar.waitForExistence(timeout: 10))
        XCTAssertTrue(marketBar.buttons.firstMatch.exists)
        let query = app.textFields["stockQuery"]
        query.tap(); query.typeText("삼성")
        let result = app.buttons["stockResult_1"]
        XCTAssertTrue(result.waitForExistence(timeout: 10)); result.tap()
        app.buttons["종목 관련 자료"].tap()
        let back = app.navigationBars.buttons.firstMatch
        XCTAssertTrue(back.waitForExistence(timeout: 10)); back.tap()
        XCTAssertTrue(app.buttons["changeStock"].waitForExistence(timeout: 10))
        app.navigationBars["종목과 단가"].buttons.firstMatch.tap()
        XCTAssertTrue(app.navigationBars["포트폴리오"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["portfolioMarket"].exists)
    }
    func testAccountRetainsRealLoginAndGuestFeedback() {
        let app = launch(); app.tabBars.buttons["내 계정"].tap()
        XCTAssertTrue(app.buttons["Google로 로그인"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["환율"].exists)
        app.buttons["openFeedback"].tap()
        let input = app.textFields["feedbackField"]
        reveal(input, in: app); input.tap(); input.typeText("UI fixture feedback")
        let send = app.buttons["sendFeedback"]; reveal(send, in: app); send.tap()
        XCTAssertTrue(app.staticTexts["의견을 보내 주셔서 감사합니다."].waitForExistence(timeout: 10))
    }
}
