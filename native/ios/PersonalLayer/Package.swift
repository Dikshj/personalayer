// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "PersonalLayer",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "PersonalLayer", targets: ["PersonalLayer"])
    ],
    dependencies: [
        .package(url: "https://github.com/groue/GRDB.swift.git", from: "6.23.0")
    ],
    targets: [
        .target(
            name: "PersonalLayer",
            dependencies: [
                .product(name: "GRDB", package: "GRDB.swift")
            ],
            path: "Sources/PersonalLayer"
        ),
        .testTarget(
            name: "PersonalLayerTests",
            dependencies: ["PersonalLayer"],
            path: "Tests/PersonalLayerTests"
        )
    ]
)
