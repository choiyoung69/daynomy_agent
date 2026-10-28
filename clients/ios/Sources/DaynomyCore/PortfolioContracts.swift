import Foundation
public enum LocalTradeType: String, Codable, Sendable { case BUY, SELL }
public enum PortfolioError: Error, Equatable, Sendable { case invalidTrade, duplicateID, notFound, oversell, precisionOverflow }
public struct LocalTrade: Equatable, Sendable {
    public var id: Int64; public var stock: Stock; public var type: LocalTradeType; public var date: String
    public var quantity: Int64; public var unitPrice: String; public var fee: String; public var tax: String; public var exchangeRate: String?
    public init(id:Int64,stock:Stock,type:LocalTradeType,date:String,quantity:Int64,unitPrice:String,fee:String="0",tax:String="0",exchangeRate:String?=nil) { self.id=id;self.stock=stock;self.type=type;self.date=date;self.quantity=quantity;self.unitPrice=unitPrice;self.fee=fee;self.tax=tax;self.exchangeRate=exchangeRate }
}
public struct LocalHolding: Equatable, Sendable {
    public let stock: Stock; public let quantity: Int64; public let averagePurchasePrice: Decimal
    public init(stock:Stock,quantity:Int64,averagePurchasePrice:Decimal) { self.stock=stock;self.quantity=quantity;self.averagePurchasePrice=averagePurchasePrice }
}
