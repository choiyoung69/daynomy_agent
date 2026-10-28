import Foundation
import Testing
@testable import DaynomyCore
func decimal(_ value:String) -> Decimal { Decimal(string:value,locale:Locale(identifier:"en_US_POSIX"))! }
func trade(_ id:Int64,type:LocalTradeType = .BUY,quantity:Int64 = 1,price:String="100",date:String="2026-10-01",fee:String="0",tax:String="0",stock:Stock=sample(),rate:String?=nil) -> LocalTrade { LocalTrade(id:id,stock:stock,type:type,date:date,quantity:quantity,unitPrice:price,fee:fee,tax:tax,exchangeRate:rate) }
struct GuestPortfolioTests {
    @Test func buyWeightedAverageIncludesFeesAndExactDecimal() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1,quantity:2,price:"100.10",fee:"0.10",tax:"0.10"))
        try engine.add(trade(2,quantity:1,price:"200.20"))
        let holding = try #require(engine.holdings().first)
        #expect(holding.quantity == 3)
        #expect(holding.averagePurchasePrice == decimal("133.53"))
        #expect(engine.trades.count == 2)
    }
    @Test func sellReducesQuantityKeepsCostAndRealizesNet() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1,quantity:3,price:"100"))
        try engine.add(trade(2,type:.SELL,quantity:2,price:"150",fee:"1",tax:"2"))
        let holding = try #require(engine.holdings().first)
        #expect(holding.quantity == 1)
        #expect(holding.averagePurchasePrice == decimal("100"))
        #expect(try engine.realizedProfitLoss() == decimal("97"))
        try engine.add(trade(3,type:.SELL,quantity:1,price:"100"))
        #expect(try engine.holdings().isEmpty)
    }
    @Test func usdRateConvertsCostAndSale() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        let stock = Stock(assetId:2,assetCode:"A.US",name:"US",market:"NASDAQ",currency:"USD")
        try engine.add(trade(1,price:"0.1001",stock:stock,rate:"1300.123456"))
        #expect(try engine.holdings().first?.averagePurchasePrice == decimal("130.14"))
        try engine.add(trade(2,type:.SELL,price:"0.2001",stock:stock,rate:"1400"))
        #expect(try engine.realizedProfitLoss() == decimal("150"))
    }
    @Test func replayDateThenIDAndOversellRollback() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(2,quantity:3,date:"2026-10-02"))
        let before = engine.trades
        do { try engine.add(trade(1,type:.SELL,date:"2026-10-01"));Issue.record("oversell accepted") } catch { #expect((error as? PortfolioError) == .oversell) }
        #expect(engine.trades == before)
        #expect(try engine.holdings().first?.quantity == 3)
    }
    @Test func editAndDeleteReplaysAllLaterTradesAtomically() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1,quantity:5))
        try engine.add(trade(2,type:.SELL,quantity:3,date:"2026-10-02"))
        let before = engine.trades
        do { try engine.update(trade(1,quantity:2));Issue.record("invalid edit accepted") } catch { #expect((error as? PortfolioError) == .oversell) }
        #expect(engine.trades == before)
        do { try engine.remove(id:1);Issue.record("invalid delete accepted") } catch { #expect((error as? PortfolioError) == .oversell) }
        #expect(engine.trades == before)
        try engine.remove(id:2)
        try engine.update(trade(1,quantity:2,price:"77.77"))
        #expect(try engine.holdings().first?.quantity == 2)
        #expect(try engine.holdings().first?.averagePurchasePrice == decimal("77.77"))
        try engine.remove(id:1)
        #expect(try engine.holdings().isEmpty)
    }
    @Test func validationRejectsBadDateQuantityAndScales() {
        let bad = [trade(1,quantity:0),trade(1,quantity:-1),trade(1,quantity:9_007_199_254_740_992),trade(1,price:"0"),trade(1,price:"0.001"),trade(1,price:"1.12345"),trade(1,price:"1e2"),trade(1,fee:"0.001"),trade(1,tax:"-1"),trade(1,date:"2026-02-30"),trade(1,date:"2026-10-29"),trade(1,date:"2026-1-1")]
        for value in bad {
            var engine = PortfolioEngine(today:"2026-10-28")
            do { try engine.add(value);Issue.record("bad trade accepted") } catch { #expect((error as? PortfolioError) == .invalidTrade) }
            #expect(engine.trades.isEmpty)
        }
    }
    @Test func usdRequiresPositiveRateAndSixFractionDigits() {
        let stock = Stock(assetId:2,assetCode:"A.US",name:"US",market:"NASDAQ")
        for rate in [Optional<String>.none,"0","-1","1.1234567"] {
            var engine = PortfolioEngine(today:"2026-10-28")
            do { try engine.add(trade(1,price:"0.0001",stock:stock,rate:rate));Issue.record("bad rate accepted") } catch { #expect((error as? PortfolioError) == .invalidTrade) }
        }
    }
    @Test func duplicateAndMissingIDAreExplicit() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1))
        do { try engine.add(trade(1));Issue.record("duplicate accepted") } catch { #expect((error as? PortfolioError) == .duplicateID) }
        do { try engine.update(trade(99));Issue.record("unknown update accepted") } catch { #expect((error as? PortfolioError) == .notFound) }
        do { try engine.remove(id:99);Issue.record("unknown delete accepted") } catch { #expect((error as? PortfolioError) == .notFound) }
    }
    @Test func openingBalanceAndNegativeProfitRoundAwayFromZero() throws {
        var engine = PortfolioEngine(openingHoldings:[LocalHolding(stock:sample(),quantity:1,averagePurchasePrice:decimal("1"))],today:"2026-10-28")
        try engine.add(trade(1,type:.SELL,price:"0.995"))
        #expect(try engine.realizedProfitLoss() == decimal("-0.01"))
    }
}
