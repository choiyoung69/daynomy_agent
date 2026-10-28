import XCTest

/// Native navigation regression; requires Xcode/iOS Simulator, not run by host harness.
@MainActor final class DaynomyFullUITests: XCTestCase {
    func testFourNativeSectionsAndGuestFeedbackEntry() {
        let app = XCUIApplication()
        app.launchEnvironment["DAYNOMY_API_BASE_URL"] = ProcessInfo.processInfo.environment["DAYNOMY_UI_BASE_URL"] ?? "http://127.0.0.1:18082"
        app.launch()
        for title in ["포트폴리오", "소식", "종목", "내 정보"] {
            let tab = app.tabBars.buttons[title]
            XCTAssertTrue(tab.waitForExistence(timeout: 5), "Missing native section \(title)")
            tab.tap()
        }
        XCTAssertTrue(app.textFields["feedbackField"].waitForExistence(timeout: 5))
        app.tabBars.buttons["소식"].tap()
        XCTAssertTrue(app.pickers["discoveryMode"].waitForExistence(timeout: 5) || app.buttons["discoveryMode"].exists)
        app.tabBars.buttons["종목"].tap()
        XCTAssertTrue(app.textFields["stockQuery"].waitForExistence(timeout: 5))
    }
}
