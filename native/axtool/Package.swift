// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "axtool",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "axtool",
            path: "Sources/axtool"
        ),
    ]
)
