public enum NewsPresentation {
    public static func items(payload: ServiceValue, isNewsSearch: Bool) -> [ServiceValue] {
        payload[isNewsSearch ? "content" : "items"]?.array ?? []
    }

    public static let adminCategoryCodes = ["STOCK", "ETF", "REAL_ESTATE"]
}
