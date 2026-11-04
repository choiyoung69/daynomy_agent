import XCTest

/// Screenshots are inspection material, not automatic visual/accessibility approval.
@MainActor final class DaynomyCommonVisualUITests: XCTestCase {
    private func captureSurfaces(accessibility: Bool) {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchEnvironment["DAYNOMY_API_BASE_URL"] = ProcessInfo.processInfo.environment["DAYNOMY_UI_BASE_URL"] ?? "http://127.0.0.1:18097"
        if accessibility {
            app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        }
        app.launch()
        let prefix = accessibility ? "accessibilityXXXL" : "normal"
        func capture(_ name: String) {
            let attachment = XCTAttachment(screenshot: app.screenshot())
            attachment.name = "\(prefix)-\(name)"
            attachment.lifetime = .keepAlways
            add(attachment)
        }
        let portfolio = app.tabBars.buttons["포트폴리오"]
        XCTAssertTrue(portfolio.waitForExistence(timeout: 10)); portfolio.tap()
        XCTAssertTrue(app.buttons["portfolioMarket"].waitForExistence(timeout: 10))
        capture("portfolio-first-entry")
        app.tabBars.buttons["이슈"].tap()
        let position = app.staticTexts["todayNewsPosition"]
        XCTAssertTrue(position.waitForExistence(timeout: 10)); XCTAssertEqual(position.label, "1 / 9")
        let loading = app.staticTexts["이미지 불러오는 중"]
        let settled = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: loading)
        XCTAssertEqual(XCTWaiter.wait(for: [settled], timeout: 10), .completed)
        capture("issue-first-photo")
        app.tabBars.buttons["내 계정"].tap()
        XCTAssertTrue(app.buttons["Google로 로그인"].waitForExistence(timeout: 10))
        capture("account-login")
    }
    func testNormalSurfaces() { captureSurfaces(accessibility: false) }
    func testAccessibilitySurfaces() { captureSurfaces(accessibility: true) }
}
