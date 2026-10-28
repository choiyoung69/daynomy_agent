// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "DaynomyIOS", platforms: [.iOS(.v17), .macOS(.v14)], products: [.library(name: "DaynomyCore", targets: ["DaynomyCore"])], targets: [.target(name: "DaynomyCore"), .testTarget(name: "DaynomyCoreTests", dependencies: ["DaynomyCore"])], swiftLanguageModes: [.v6])
