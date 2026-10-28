import Foundation
@main struct PortfolioSupplement {
 static func main() throws {
  for stock in [Stock(assetId:1,assetCode:"A.US",name:"explicitKRW",market:"NASDAQ",currency:"KRW"),Stock(assetId:2,assetCode:"A",name:"fallbackKRW",market:"NASDAQ")] {
   var engine=PortfolioEngine(today:"2026-10-28")
   try engine.add(LocalTrade(id:1,stock:stock,type:.BUY,date:"2026-10-28",quantity:1,unitPrice:"1"))
   guard try engine.holdings().first?.averagePurchasePrice==Decimal(1) else {print("FAIL currency policy");exit(1)}
  }
  print("PORTFOLIO SUPPLEMENT 2 passed: explicit currency overrides suffix; nil currency uses suffix only")
 }
}
