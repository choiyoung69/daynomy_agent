import UIKit
import WebKit

final class WebViewController: UIViewController, WKNavigationDelegate, WKUIDelegate {
    private var webView: WKWebView?
    private var policy: NavigationPolicy?
    private var origin = ""
    private var observers: [NSObjectProtocol] = []
    private var active = true
    private var processEnded = false
    private var loadFailed = false
    private let errorLabel = UILabel()
    private let retryButton = UIButton(type: .system)
    private let errorPanel = UIStackView()
    private var pendingRules: WKContentRuleList?

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "DAYNOMY · WebView"
        view.backgroundColor = .systemBackground
        navigationItem.leftBarButtonItem = UIBarButtonItem(title: "뒤로", style: .plain, target: self, action: #selector(goBack))
        errorLabel.numberOfLines = 0
        errorLabel.accessibilityTraits = .staticText
        retryButton.setTitle("다시 시도", for: .normal)
        retryButton.addTarget(self, action: #selector(retry), for: .touchUpInside)
        retryButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 48).isActive = true
        errorPanel.axis = .vertical
        errorPanel.spacing = 12
        errorPanel.addArrangedSubview(errorLabel)
        errorPanel.addArrangedSubview(retryButton)
        errorPanel.isHidden = true
        errorPanel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(errorPanel)
        NSLayoutConstraint.activate([
            errorPanel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 20),
            errorPanel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -20),
            errorPanel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16)
        ])
        #if DEBUG
        origin = Bundle.main.object(forInfoDictionaryKey: "DAYNOMYWebOrigin") as? String ?? "http://127.0.0.1:18082"
        let debug = true
        #else
        origin = Bundle.main.object(forInfoDictionaryKey: "DAYNOMYWebOrigin") as? String ?? ""
        let debug = false
        #endif
        guard NavigationPolicy.isValidConfiguration(origin, debug: debug) else {
            showError("앱의 HTTPS 웹 주소를 설정해야 합니다.")
            retryButton.isEnabled = false
            return
        }
        policy = NavigationPolicy(trustedOrigin: origin, debug: debug)
        configureContentRules()
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { [weak self] _ in self?.setActive(false) })
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in self?.setActive(true) })
    }

    private func configureContentRules() {
        // Main-frame and subframe document navigation is guarded by the delegate.
        // Deny all other remote resources except the exact configured origin (including port).
        // Transport debug allowances never grant additional navigable/resource origins.
        guard let url = URL(string: origin), let scheme = url.scheme, let host = url.host else { return }
        let hostPattern = NSRegularExpression.escapedPattern(for: host)
        let defaultPort = scheme == "https" ? 443 : 80
        let portPattern = url.port.map { $0 == defaultPort ? "(:\($0))?" : ":\($0)" } ?? "(:\(defaultPort))?"
        let pattern = "^\(scheme)://\(hostPattern)\(portPattern)(/|$)"
        let rules: [[String: Any]] = [
            ["trigger": ["url-filter": ".*", "resource-type": ["image", "style-sheet", "script", "font", "media", "raw", "svg-document", "popup", "ping"]], "action": ["type": "block"]],
            ["trigger": ["url-filter": pattern, "url-filter-is-case-sensitive": false], "action": ["type": "ignore-previous-rules"]]
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: rules), let json = String(data: data, encoding: .utf8) else { return }
        WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "daynomy-exact-origin", encodedContentRuleList: json) { [weak self] rules, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard let rules = rules else { self.showError("웹 보안 정책을 준비하지 못했습니다."); return }
                self.pendingRules = rules
                self.createWebView()
                self.loadHome()
            }
        }
    }
    private func createWebView() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
        if let rules = pendingRules { configuration.userContentController.add(rules) }
        // No WKScriptMessageHandler/native privilege bridge is registered.
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        web.scrollView.keyboardDismissMode = .interactive
        web.translatesAutoresizingMaskIntoConstraints = false
        view.insertSubview(web, belowSubview: errorPanel)
        NSLayoutConstraint.activate([
            web.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            web.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            web.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            web.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor)
        ])
        webView = web
        processEnded = false
    }
    private func loadHome() { if let url = URL(string: origin + "/") { webView?.load(URLRequest(url: url)) } }
    @objc private func goBack() { if webView?.canGoBack == true { webView?.goBack() } }
    @objc private func retry() {
        guard policy != nil else { return }
        if pendingRules == nil { configureContentRules() }
        else if processEnded || webView == nil { webView?.removeFromSuperview(); createWebView(); loadHome() }
        else { webView?.reload() }
    }
    private func showError(_ message: String) {
        errorLabel.text = message
        errorPanel.isHidden = false
        UIAccessibility.post(notification: .announcement, argument: message)
    }
    private func setActive(_ value: Bool) {
        active = value
        webView?.evaluateJavaScript("window.dispatchEvent(new CustomEvent('daynomy:active',{detail:\(value ? "true" : "false")}));", completionHandler: nil)
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url, let target = navigationAction.targetFrame, target.isMainFrame else { decisionHandler(.cancel); return }
        let user = navigationAction.navigationType == .linkActivated
        switch policy?.decide(url.absoluteString, userActivated: user) ?? .block {
        case .internalPage: decisionHandler(.allow)
        case .externalBrowser:
            decisionHandler(.cancel)
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        case .block: decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if navigationResponse.isForMainFrame, let response = navigationResponse.response as? HTTPURLResponse, response.statusCode >= 400 {
            loadFailed = true
            showError("페이지 응답에 문제가 있습니다. 다시 시도해 주세요.")
            decisionHandler(.cancel)
        } else { decisionHandler(.allow) }
    }
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { loadFailed = false }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { if !loadFailed { errorPanel.isHidden = true }; setActive(active) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { pageFailed(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { pageFailed(error) }
    private func pageFailed(_ error: Error) {
        if (error as NSError).code == NSURLErrorCancelled { return }
        loadFailed = true
        showError("페이지를 불러오지 못했습니다. 연결을 확인하고 다시 시도해 주세요.")
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        processEnded = true
        showError("웹 화면이 종료되었습니다. 다시 시도해 주세요. 저장하지 않은 입력은 복원되지 않을 수 있습니다.")
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? { nil }
    // TLS challenges use WebKit's normal verification; no trust bypass handler exists.
    deinit { observers.forEach { NotificationCenter.default.removeObserver($0) }; webView?.stopLoading() }
}
