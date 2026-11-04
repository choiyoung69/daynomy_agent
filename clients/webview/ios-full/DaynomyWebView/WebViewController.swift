import UIKit
import WebKit
import AuthenticationServices
import Security

final class WebViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, ASWebAuthenticationPresentationContextProviding {
    private var webView: WKWebView?
    private var policy: NavigationPolicy?
    private var resourcesPolicy: FullResourcePolicy?
    private var webDialog: UIAlertController?
    private var dialogCompletion: ((Bool) -> Void)?
    private var origin = ""
    private var observers: [NSObjectProtocol] = []
    private var active = true
    private var processEnded = false
    private var loadFailed = false
    private let errorLabel = UILabel()
    private let retryButton = UIButton(type: .system)
    private let errorPanel = UIStackView()
    private var pendingRules: WKContentRuleList?
    private var nativeAuth: NativeAuthSession?
    private var authBrowser: ASWebAuthenticationSession?
    private var authHTTP: URLSession?
    private var authTask: URLSessionDataTask?
    private var authGeneration: UInt64 = 0
    private var authPending = false
    private var cookieInstalling = false
    private var cookieRollback = false
    private var cookieOwner: UUID?
    private var authTimeout: DispatchWorkItem?

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
        resourcesPolicy = FullResourcePolicy(trustedOrigin: origin, debug: debug)
        nativeAuth = NativeAuthSession(trustedOrigin: origin, debug: debug)
        configureContentRules()
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { [weak self] _ in self?.setActive(false) })
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in self?.setActive(true) })
    }

    private func configureContentRules() {
        // Documents are checked by the navigation delegate. HTTPS assets may cross origins,
        // while page CSP, SOP, engine TLS validation and ordinary cookie rules still apply.
        guard let url = URL(string: origin), let scheme = url.scheme, let host = url.host else { return }
        let hostPattern = NSRegularExpression.escapedPattern(for: host)
        let defaultPort = scheme == "https" ? 443 : 80
        let portPattern = url.port.map { $0 == defaultPort ? "(:\($0))?" : ":\($0)" } ?? "(:\(defaultPort))?"
        let pattern = "^\(scheme)://\(hostPattern)\(portPattern)/"
        // WebKit content rules accept a restricted regex subset. Avoid alternation,
        // counted quantifiers, and nested end anchors; enumerate valid port ranges.
        let ports = ["", ":[1-9][0-9]?[0-9]?[0-9]?", ":[1-5][0-9][0-9][0-9][0-9]", ":6[0-4][0-9][0-9][0-9]", ":65[0-4][0-9][0-9]", ":655[0-2][0-9]", ":6553[0-5]"]
        let hosts = ["[a-z0-9-]+(\\.[a-z0-9-]+)*", "\\[[a-f0-9:]+\\]"]
        var rules: [[String: Any]] = [
            ["trigger": ["url-filter": ".*", "resource-type": ["image", "style-sheet", "script", "font", "media", "raw", "svg-document", "popup", "ping"]], "action": ["type": "block"]]
        ]
        for host in hosts {
            for port in ports {
                rules.append(["trigger": ["url-filter": "^https://" + host + port + "/", "url-filter-is-case-sensitive": false], "action": ["type": "ignore-previous-rules"]])
            }
        }
        rules.append(["trigger": ["url-filter": pattern, "url-filter-is-case-sensitive": false], "action": ["type": "ignore-previous-rules"]])
        // Native picker previews stay ordinary web-owned images, without file URL access.
        rules.append(["trigger": ["url-filter": "^blob:" + String(pattern.dropFirst()), "resource-type": ["image"], "url-filter-is-case-sensitive": false], "action": ["type": "ignore-previous-rules"]])
        rules.append(["trigger": ["url-filter": "^data:image/", "resource-type": ["image"]], "action": ["type": "ignore-previous-rules"]])
        guard let data = try? JSONSerialization.data(withJSONObject: rules), let json = String(data: data, encoding: .utf8) else { return }
        WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "daynomy-full-https-resources", encodedContentRuleList: json) { [weak self] rules, _ in
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
    private func loadHome() {
        guard !NativeAuthCookieTransaction.busy else { showError("이전 로그인 정리를 마친 뒤 다시 시도를 눌러 주세요."); return }
        if let url = URL(string: origin + "/") { webView?.load(URLRequest(url: url)) }
    }
    @objc private func goBack() { cancelNativeAuth(); if !NativeAuthCookieTransaction.busy, webView?.canGoBack == true { webView?.goBack() } }
    @objc private func retry() {
        cancelNativeAuth()
        guard !NativeAuthCookieTransaction.busy else { showError("로그인 정리를 마친 뒤 다시 시도를 눌러 주세요."); return }
        guard policy != nil else { return }
        if pendingRules == nil { configureContentRules() }
        else if processEnded || webView == nil { webView?.removeFromSuperview(); createWebView(); loadHome() }
        else if webView?.url == nil { loadHome() } else { webView?.reload() }
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
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        let user = navigationAction.navigationType == .linkActivated
        guard let target = navigationAction.targetFrame else {
            decisionHandler(.cancel)
            if user, navigationAction.sourceFrame.isMainFrame,
               policy?.decide(navigationAction.sourceFrame.request.url?.absoluteString ?? "", userActivated: false) == .internalPage,
               policy?.decide(url.absoluteString, userActivated: true) == .externalBrowser {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
            return
        }
        if !target.isMainFrame {
            decisionHandler(resourcesPolicy?.allows(url.absoluteString, isMainFrame: false) == true ? .allow : .cancel)
            return
        }
        if startNativeAuth(webView, action: navigationAction) { decisionHandler(.cancel); return }
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
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        if authPending || cookieInstalling { cancelNativeAuth() }
        cancelWebDialog(); loadFailed = false
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { if !loadFailed { errorPanel.isHidden = true }; setActive(active) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { pageFailed(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { pageFailed(error) }
    private func pageFailed(_ error: Error) {
        if (error as NSError).code == NSURLErrorCancelled { return }
        loadFailed = true
        showError("페이지를 불러오지 못했습니다. 연결을 확인하고 다시 시도해 주세요.")
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        cancelNativeAuth()
        cancelWebDialog()
        processEnded = true
        showError("웹 화면이 종료되었습니다. 다시 시도해 주세요. 저장하지 않은 입력은 복원되지 않을 수 있습니다.")
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? { nil }
    private func cancelWebDialog() {
        let completion = dialogCompletion; dialogCompletion = nil
        webDialog?.dismiss(animated: false); webDialog = nil
        completion?(false)
    }
    private func showWebDialog(message: String, frame: WKFrameInfo, confirm: Bool, completion: @escaping (Bool) -> Void) {
        cancelWebDialog()
        guard frame.isMainFrame,
              policy?.decide(frame.request.url?.absoluteString ?? "", userActivated: false) == .internalPage,
              viewIfLoaded?.window != nil else { completion(false); return }
        dialogCompletion = completion
        let dialog = UIAlertController(title: "DAYNOMY", message: message, preferredStyle: .alert)
        let complete: (Bool) -> Void = { [weak self] accepted in
            guard let self = self else { return }
            let pending = self.dialogCompletion; self.dialogCompletion = nil; self.webDialog = nil
            pending?(accepted)
        }
        dialog.addAction(UIAlertAction(title: "확인", style: .default) { _ in complete(true) })
        if confirm { dialog.addAction(UIAlertAction(title: "취소", style: .cancel) { _ in complete(false) }) }
        webDialog = dialog
        present(dialog, animated: true)
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        showWebDialog(message: message, frame: frame, confirm: false) { _ in completionHandler() }
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        showWebDialog(message: message, frame: frame, confirm: true, completion: completionHandler)
    }
    // WKWebView's standard file input UI remains OS-mediated; no custom filesystem picker.
    // TLS challenges use WebKit's normal verification; no trust bypass handler exists.
    private var authNow: Int64 { Int64(ProcessInfo.processInfo.systemUptime * 1000) }
    private func randomAuthValue() -> String? {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { return nil }
        return Data(bytes).base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
    private func startNativeAuth(_ webView: WKWebView, action: WKNavigationAction) -> Bool {
        guard let navigation = action.request.url, navigation.path == "/api/auth/google",
              policy?.decide(navigation.absoluteString, userActivated: false) == .internalPage else { return false }
        if authPending || cookieInstalling || NativeAuthCookieTransaction.busy { showError("로그인이 진행 중입니다. 잠시 후 다시 시도해 주세요."); return true }
        guard let state = randomAuthValue(), let verifier = randomAuthValue(),
              action.sourceFrame.isMainFrame,
              let launch = nativeAuth?.begin(navigationURL: navigation.absoluteString, sourceDocumentURL: webView.url?.absoluteString ?? "",
                  httpMethod: action.request.httpMethod ?? "GET", isMainFrame: action.targetFrame?.isMainFrame == true,
                  userActivated: action.navigationType == .linkActivated, state: state, verifier: verifier, nowMillis: authNow),
              let authorizationURL = URL(string: launch.authorizationURL) else { showError("로그인 버튼을 눌러 다시 시작해 주세요."); return true }
        authGeneration &+= 1
        let generation = authGeneration
        authPending = true
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "로그인 취소", style: .plain, target: self, action: #selector(cancelLogin))
        // WK navigation delegates do not observe SPA logout/fetch. Keep native cancellation available,
        // but prevent page actions from racing the native session transaction.
        webView.isUserInteractionEnabled = false
        let timeout = DispatchWorkItem { [weak self] in
            guard let self = self, generation == self.authGeneration else { return }
            self.cancelNativeAuth(); self.showError("로그인 시간이 만료됐습니다. 다시 시도해 주세요.")
        }
        authTimeout = timeout
        DispatchQueue.main.asyncAfter(deadline: .now() + 600, execute: timeout)
        let browser = ASWebAuthenticationSession(url: authorizationURL, callbackURLScheme: "org.daynomy.app") { [weak self] callback, error in
            DispatchQueue.main.async {
                guard let self = self, generation == self.authGeneration else { return }
                self.authBrowser = nil
                guard error == nil, let callback = callback else {
                    self.cancelNativeAuth(); self.showError("로그인이 취소되었거나 완료되지 않았습니다."); return
                }
                guard let exchange = self.nativeAuth?.receive(callbackURL: callback.absoluteString, nowMillis: self.authNow) else {
                    if self.nativeAuth?.isPending != true { self.cancelNativeAuth() }
                    self.showError("로그인을 완료하지 못했습니다. 다시 시도해 주세요."); return
                }
                self.exchangeNativeAuth(exchange, generation: generation)
            }
        }
        browser.presentationContextProvider = self
        browser.prefersEphemeralWebBrowserSession = true
        authBrowser = browser
        if !browser.start() { cancelNativeAuth(); showError("로그인 브라우저를 열지 못했습니다.") }
        return true
    }
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor { view.window ?? ASPresentationAnchor() }
    private func exchangeNativeAuth(_ exchange: AuthExchange, generation: UInt64) {
        guard let url = URL(string: exchange.exchangeURL),
              let body = try? JSONSerialization.data(withJSONObject: ["code": exchange.code, "codeVerifier": exchange.codeVerifier]) else { cancelNativeAuth(); return }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.urlCache = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        let transport = URLSession(configuration: configuration, delegate: NativeAuthRedirectBlocker(), delegateQueue: nil)
        authHTTP = transport
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = body
        authTask = transport.dataTask(with: request) { [weak self] _, response, error in
            DispatchQueue.main.async {
                guard let self = self, generation == self.authGeneration else { return }
                guard error == nil, let response = response as? HTTPURLResponse,
                      let plan = self.nativeAuth?.complete(requestId: exchange.requestId, status: response.statusCode,
                          responseURL: response.url?.absoluteString ?? "", setCookieHeaders: Self.nativeCookieHeaders(response), nowMillis: self.authNow) else {
                    self.cancelNativeAuth(); self.showError("로그인 세션을 연결하지 못했습니다. 다시 시도해 주세요."); return
                }
                self.authHTTP?.finishTasksAndInvalidate(); self.authHTTP = nil; self.authTask = nil
                self.installNativeCookies(plan, generation: generation)
            }
        }
        authTask?.resume()
    }
    private static func nativeCookieHeaders(_ response: HTTPURLResponse) -> [String] {
        // Foundation may combine duplicate Set-Cookie fields. Split only a following session-cookie boundary,
        // never arbitrary commas inside a value; the pure validator still rejects malformed values/attributes.
        let boundary = try? NSRegularExpression(pattern: ",(?=\\s*(?:access_token|refresh_token)=)", options: [.caseInsensitive])
        return response.allHeaderFields.filter { String(describing: $0.key).lowercased() == "set-cookie" }.flatMap { entry -> [String] in
            let values = (entry.value as? [String]) ?? [String(describing: entry.value)]
            return values.flatMap { value -> [String] in
                guard !value.contains("\n"), !value.contains("\r") else { return [value] }
                guard let boundary = boundary else { return [value] }
                let marked = boundary.stringByReplacingMatches(in: value, range: NSRange(value.startIndex..., in: value), withTemplate: "\n")
                return marked.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
            }
        }
    }
    private func installNativeCookies(_ plan: AuthCookiePlan, generation: UInt64) {
        guard let originURL = URL(string: plan.originURL), let store = webView?.configuration.websiteDataStore.httpCookieStore else { cancelNativeAuth(); return }
        let cookies = plan.setCookieHeaders.flatMap { HTTPCookie.cookies(withResponseHeaderFields: ["Set-Cookie": $0], for: originURL) }
        guard cookies.count == 2, cookies.allSatisfy({ $0.isHTTPOnly }) else { cancelNativeAuth(); showError("로그인 쿠키를 저장하지 못했습니다."); return }
        let owner = UUID()
        guard NativeAuthCookieTransaction.acquire(owner) else { cancelNativeAuth(); showError("로그인 저장을 마칠 때까지 잠시 기다려 주세요."); return }
        cookieOwner = owner
        cookieInstalling = true
        cookieRollback = false
        func next(_ index: Int) {
            guard generation == authGeneration, viewIfLoaded?.window != nil else { rollbackNativeCookies(cookies, store: store); return }
            if index == cookies.count {
                store.getAllCookies { [weak self] stored in
                    DispatchQueue.main.async {
                        guard let self = self else { Self.deleteNativeCookies(cookies, store: store) { NativeAuthCookieTransaction.release(owner) }; return }
                        guard generation == self.authGeneration else { self.rollbackNativeCookies(cookies, store: store); return }
                        let present = cookies.allSatisfy { expected in stored.contains { actual in
                            actual.name == expected.name && actual.domain == expected.domain && actual.path == expected.path &&
                            actual.value == expected.value && actual.isHTTPOnly && actual.isSecure == expected.isSecure
                        } }
                        guard present, let reload = URL(string: plan.reloadURL) else { self.cancelNativeAuth(); self.rollbackNativeCookies(cookies, store: store); self.showError("로그인 쿠키를 확인하지 못했습니다."); return }
                        self.cookieInstalling = false; self.authPending = false; self.authTimeout?.cancel(); self.authTimeout = nil
                        self.webView?.isUserInteractionEnabled = true
                        self.navigationItem.rightBarButtonItem = nil
                        NativeAuthCookieTransaction.release(owner); self.cookieOwner = nil
                        self.webView?.load(URLRequest(url: reload))
                    }
                }
                return
            }
            store.setCookie(cookies[index]) { [weak self] in
                DispatchQueue.main.async {
                    guard let self = self else { Self.deleteNativeCookies(cookies, store: store) { NativeAuthCookieTransaction.release(owner) }; return }
                    guard generation == self.authGeneration else { self.rollbackNativeCookies(cookies, store: store); return }
                    next(index + 1)
                }
            }
        }
        next(0)
    }
    private func rollbackNativeCookies(_ cookies: [HTTPCookie], store: WKHTTPCookieStore) {
        if cookieRollback { return }
        cookieRollback = true
        let owner = cookieOwner
        Self.deleteNativeCookies(cookies, store: store) { [weak self] in
            DispatchQueue.main.async {
                if let owner = owner { NativeAuthCookieTransaction.release(owner) }
                self?.cookieInstalling = false; self?.cookieRollback = false; self?.cookieOwner = nil
                self?.webView?.isUserInteractionEnabled = true
            }
        }
    }
    private static func deleteNativeCookies(_ cookies: [HTTPCookie], store: WKHTTPCookieStore, completion: @escaping () -> Void) {
        func remove(_ index: Int) {
            if index == cookies.count { completion(); return }
            store.delete(cookies[index]) { remove(index + 1) }
        }
        remove(0)
    }
    private func cancelNativeAuth() {
        authGeneration &+= 1
        authPending = false
        navigationItem.rightBarButtonItem = nil
        nativeAuth?.cancel()
        authTimeout?.cancel(); authTimeout = nil
        authBrowser?.cancel(); authBrowser = nil
        authTask?.cancel(); authTask = nil
        authHTTP?.invalidateAndCancel(); authHTTP = nil
        if !cookieInstalling { webView?.isUserInteractionEnabled = true }
        // Cookie installation callbacks detect generation changes and remove only the two session cookies.
    }
    @objc private func cancelLogin() { cancelNativeAuth(); showError("로그인을 취소했습니다. 다시 시도할 수 있습니다.") }
    deinit {
        authBrowser?.cancel(); authTask?.cancel(); authHTTP?.invalidateAndCancel(); authTimeout?.cancel()
        nativeAuth?.cancel(); dialogCompletion?(false)
        observers.forEach { NotificationCenter.default.removeObserver($0) }; webView?.stopLoading()
    }
}

/// All callers use the main queue; the default WebKit cookie store outlives individual controllers.
private enum NativeAuthCookieTransaction {
    private static var owner: UUID?
    static var busy: Bool { owner != nil }
    static func acquire(_ candidate: UUID) -> Bool { guard owner == nil else { return false }; owner = candidate; return true }
    static func release(_ candidate: UUID) { if owner == candidate { owner = nil } }
}

private final class NativeAuthRedirectBlocker: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
