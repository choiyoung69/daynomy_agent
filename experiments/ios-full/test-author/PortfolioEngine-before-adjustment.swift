import Foundation

/// Replays a proposed ledger before committing it, so every mutation is atomic.
public struct PortfolioEngine: Sendable {
    public private(set) var trades: [LocalTrade] = []
    private let openingHoldings: [LocalHolding]
    private let today: String
    public init(openingHoldings: [LocalHolding] = [], today: String) {
        self.openingHoldings = openingHoldings; self.today = today
    }
    public mutating func add(_ trade: LocalTrade) throws {
        guard !trades.contains(where: { $0.id == trade.id }) else { throw PortfolioError.duplicateID }
        try commit(trades + [trade])
    }
    public mutating func update(_ trade: LocalTrade) throws {
        guard let index = trades.firstIndex(where: { $0.id == trade.id }) else { throw PortfolioError.notFound }
        var proposal = trades; proposal[index] = trade; try commit(proposal)
    }
    public mutating func remove(id: Int64) throws {
        guard trades.contains(where: { $0.id == id }) else { throw PortfolioError.notFound }
        try commit(trades.filter { $0.id != id })
    }
    public func holdings() throws -> [LocalHolding] { try replay(trades).0 }
    public func realizedProfitLoss() throws -> Decimal { try rounded(replay(trades).1) }
    private mutating func commit(_ proposal: [LocalTrade]) throws {
        _ = try replay(proposal)
        trades = proposal.sorted { $0.date == $1.date ? $0.id < $1.id : $0.date < $1.date }
    }
    private func replay(_ proposal: [LocalTrade]) throws -> ([LocalHolding], Decimal) {
        var positions: [Int64: LocalHolding] = [:]
        for holding in openingHoldings {
            guard holding.quantity > 0, holding.quantity <= 9_007_199_254_740_991,
                  holding.averagePurchasePrice > 0, !holding.averagePurchasePrice.isNaN,
                  positions[holding.stock.assetId] == nil else { throw PortfolioError.invalidTrade }
            positions[holding.stock.assetId] = holding
        }
        var realized = Decimal.zero
        for trade in proposal.sorted(by: { $0.date == $1.date ? $0.id < $1.id : $0.date < $1.date }) {
            let values = try validated(trade)
            let current = positions[trade.stock.assetId]
            let gross = try operation(values.0, Decimal(trade.quantity), .multiply)
            let costs = try operation(values.1, values.2, .add)
            switch trade.type {
            case .BUY:
                let oldQuantity = current?.quantity ?? 0
                let (quantity, overflow) = oldQuantity.addingReportingOverflow(trade.quantity)
                guard !overflow, quantity <= 9_007_199_254_740_991 else { throw PortfolioError.precisionOverflow }
                let oldCost = try operation(current?.averagePurchasePrice ?? 0, Decimal(oldQuantity), .multiply)
                let nativeCost = try operation(gross, costs, .add)
                let newCost = try operation(nativeCost, values.3, .multiply)
                let total = try operation(oldCost, newCost, .add)
                let average = try rounded(operation(total, Decimal(quantity), .divide))
                positions[trade.stock.assetId] = LocalHolding(stock: trade.stock, quantity: quantity, averagePurchasePrice: average)
            case .SELL:
                guard let current, current.quantity >= trade.quantity else { throw PortfolioError.oversell }
                let nativeProceeds = try operation(gross, costs, .subtract)
                let proceeds = try operation(nativeProceeds, values.3, .multiply)
                let basis = try operation(current.averagePurchasePrice, Decimal(trade.quantity), .multiply)
                realized = try operation(realized, operation(proceeds, basis, .subtract), .add)
                let remaining = current.quantity - trade.quantity
                if remaining == 0 { positions.removeValue(forKey: trade.stock.assetId) }
                else { positions[trade.stock.assetId] = LocalHolding(stock: current.stock, quantity: remaining, averagePurchasePrice: current.averagePurchasePrice) }
            }
        }
        return (positions.values.sorted { $0.stock.assetId < $1.stock.assetId }, realized)
    }
    private func validated(_ trade: LocalTrade) throws -> (Decimal, Decimal, Decimal, Decimal) {
        guard trade.quantity > 0, trade.quantity <= 9_007_199_254_740_991,
              trade.stock.assetId > 0, trade.stock.assetId <= 9_007_199_254_740_991, trade.date <= today,
              trade.date.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil else { throw PortfolioError.invalidTrade }
        let parts = trade.date.split(separator: "-").compactMap { Int($0) }
        var calendar = Calendar(identifier: .gregorian); calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        guard parts.count == 3, parts[0] > 0,
              let date = calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2])),
              calendar.component(.year, from: date) == parts[0], calendar.component(.month, from: date) == parts[1],
              calendar.component(.day, from: date) == parts[2] else { throw PortfolioError.invalidTrade }
        let usd = (trade.stock.currency ?? (trade.stock.assetCode.hasSuffix(".US") ? "USD" : "KRW")) == "USD"
        let price = try parse(trade.unitPrice, whole: 15, scale: 4)
        let fee = try parse(trade.fee, whole: 15, scale: 2)
        let tax = try parse(trade.tax, whole: 15, scale: 2)
        guard price >= (usd ? Decimal(string: "0.0001")! : Decimal(string: "0.01")!) else { throw PortfolioError.invalidTrade }
        var rate = Decimal(1)
        if usd {
            guard let input = trade.exchangeRate else { throw PortfolioError.invalidTrade }
            rate = try parse(input, whole: 10, scale: 6)
            guard rate > 0 else { throw PortfolioError.invalidTrade }
        }
        return (price, fee, tax, rate)
    }
    private func parse(_ text: String, whole: Int, scale: Int) throws -> Decimal {
        guard text.range(of: "^[0-9]{1,\(whole)}(\\.[0-9]{1,\(scale)})?$", options: .regularExpression) != nil,
              let value = Decimal(string: text, locale: Locale(identifier: "en_US_POSIX")), !value.isNaN else { throw PortfolioError.invalidTrade }
        return value
    }
    private enum MathOperation { case add, subtract, multiply, divide }
    private func operation(_ lhs: Decimal, _ rhs: Decimal, _ op: MathOperation) throws -> Decimal {
        var lhs = lhs, rhs = rhs, result = Decimal()
        let status: Decimal.CalculationError
        switch op {
        case .add: status = NSDecimalAdd(&result, &lhs, &rhs, .plain)
        case .subtract: status = NSDecimalSubtract(&result, &lhs, &rhs, .plain)
        case .multiply: status = NSDecimalMultiply(&result, &lhs, &rhs, .plain)
        case .divide: status = NSDecimalDivide(&result, &lhs, &rhs, .plain)
        }
        // Division is intentionally rounded to cents immediately; recurring fractions are expected.
        guard status == .noError || (op == .divide && status == .lossOfPrecision), !result.isNaN else { throw PortfolioError.precisionOverflow }
        return result
    }
    private func rounded(_ input: Decimal) throws -> Decimal {
        guard !input.isNaN else { throw PortfolioError.precisionOverflow }
        var value = input, result = Decimal(); NSDecimalRound(&result, &value, 2, .plain)
        return result
    }
}
