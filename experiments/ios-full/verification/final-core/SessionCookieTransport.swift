import Foundation

/// Optional transport capability for the app's private URLSession cookie jar.
public protocol SessionCookieTransport: HTTPTransport {
    func clearSessionCookies() async
}
