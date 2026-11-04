import Foundation

@main struct NewsRouteContract {
    static func main() {
        var failures = 0
        let cases: [(String, String?)] = [
            ("/news/71", "71"),
            ("/news/72", "72"),
            ("https://untrusted.example/news/71", nil),
            ("//untrusted.example/news/71", nil),
            ("news/71", nil),
            ("/news/71?redirect=https://untrusted.example", nil),
            ("/news/71#other", nil),
            ("/news//71", nil),
            ("/news/71/", nil),
            ("/news/%37%31", nil),
            ("/news/0", nil),
            ("/news/-1", nil),
            ("/news/not-a-number", nil),
            ("/news/9223372036854775808", nil),
            ("/videos/71", nil),
            ("/news/71/extra", nil),
        ]
        for (path, expected) in cases {
            let passed = relatedNewsID(path) == expected
            print("\(passed ? "PASS" : "FAIL") internal news route \(path)")
            if !passed { failures += 1 }
        }
        print("NEWS ROUTE CONTRACT \(cases.count) checks; failures \(failures)")
        exit(failures == 0 ? 0 : 1)
    }
}
