// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "PersonalLayerSDK",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "PersonalLayerSDK", targets: ["PersonalLayerSDK"])
    ],
    dependencies: [],
    targets: [
        .target(name: "PersonalLayerSDK", path: "Sources/PersonalLayerSDK"),
        .testTarget(name: "PersonalLayerSDKTests", dependencies: ["PersonalLayerSDK"], path: "Tests/PersonalLayerSDKTests")
    ]
)
