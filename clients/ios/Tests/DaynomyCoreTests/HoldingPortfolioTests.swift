import Foundation
import Testing
@testable import DaynomyCore
func adjustment(_ id:Int64,quantity:Int64=3,average:String="50.25",date:String="2026-10-02",kind:HoldingAdjustmentKind = .adjusted) -> HoldingAdjustment { HoldingAdjustment(id:id,stock:sample(),date:date,quantity:quantity,averagePurchasePrice:average,kind:kind) }
struct HoldingPortfolioTests {
    @Test func combinedChronologicalAdjustAndRemoveReplay() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1,quantity:10,price:"100",date:"2026-10-01"))
        try engine.changeHolding(adjustment(2))
        try engine.add(trade(3,type:.SELL,quantity:2,price:"100",date:"2026-10-03"))
        #expect(try engine.holdings().first?.quantity == 1)
        #expect(try engine.holdings().first?.averagePurchasePrice == decimal("50.25"))
        #expect(try engine.realizedProfitLoss() == decimal("99.50"))
        try engine.changeHolding(adjustment(4,quantity:0,average:"0",date:"2026-10-04",kind:.removed))
        #expect(try engine.holdings().isEmpty)
        #expect(engine.holdingChanges.count == 2)
    }
    @Test func backdatedAdjustmentOversellRollsBack() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1,quantity:10))
        try engine.add(trade(3,type:.SELL,quantity:5,date:"2026-10-03"))
        for value in [adjustment(2,quantity:2),adjustment(2,quantity:0,average:"0",kind:.removed)] {
            do { try engine.changeHolding(value);Issue.record("oversell adjustment committed") } catch { #expect((error as? PortfolioError) == .oversell) }
            #expect(engine.holdingChanges.isEmpty)
            #expect(try engine.holdings().first?.quantity == 5)
        }
    }
    @Test func tradeMutationsRespectLaterAdjustment() throws {
        var engine = PortfolioEngine(today:"2026-10-28")
        try engine.add(trade(1,quantity:1))
        try engine.changeHolding(adjustment(2,quantity:10))
        try engine.add(trade(3,type:.SELL,quantity:8,date:"2026-10-03"))
        try engine.remove(id:1)
        #expect(try engine.holdings().first?.quantity == 2)
        #expect(engine.holdingChanges.count == 1)
        try engine.update(trade(3,type:.SELL,quantity:9,date:"2026-10-03"))
        #expect(try engine.holdings().first?.quantity == 1)
    }
    @Test func adjustmentValidationAndGlobalIDs() throws {
        for value in [adjustment(1,quantity:0),adjustment(1,quantity:-1),adjustment(1,quantity:9_007_199_254_740_992),adjustment(1,average:"0"),adjustment(1,average:"1.123"),adjustment(1,date:"2026-02-30"),adjustment(1,date:"2026-10-29")] {
            var engine=PortfolioEngine(today:"2026-10-28")
            do {try engine.changeHolding(value);Issue.record("bad adjustment accepted")} catch {#expect((error as? PortfolioError) == .invalidTrade)}
        }
        var engine=PortfolioEngine(today:"2026-10-28");try engine.add(trade(1))
        do {try engine.changeHolding(adjustment(1));Issue.record("global ID collision accepted")} catch {#expect((error as? PortfolioError) == .duplicateID)}
        try engine.changeHolding(adjustment(2))
        do {try engine.add(trade(2));Issue.record("reverse ID collision accepted")} catch {#expect((error as? PortfolioError) == .duplicateID)}
    }
}
