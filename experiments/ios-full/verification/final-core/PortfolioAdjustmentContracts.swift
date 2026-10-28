import Foundation
public enum HoldingAdjustmentKind: Sendable { case adjusted, removed }
public struct HoldingAdjustment: Equatable, Sendable {
    public let id: Int64; public let stock: Stock; public let date: String
    public let quantity: Int64; public let averagePurchasePrice: String; public let kind: HoldingAdjustmentKind
    public init(id:Int64,stock:Stock,date:String,quantity:Int64,averagePurchasePrice:String,kind:HoldingAdjustmentKind) { self.id=id;self.stock=stock;self.date=date;self.quantity=quantity;self.averagePurchasePrice=averagePurchasePrice;self.kind=kind }
}
