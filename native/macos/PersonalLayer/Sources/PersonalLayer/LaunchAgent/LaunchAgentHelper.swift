import Foundation

/// Manages the run-on-login LaunchAgent for Personal Layer.
/// Creates a .plist in ~/Library/LaunchAgents and loads/unloads via launchctl.
final class LaunchAgentHelper {
    static let shared = LaunchAgentHelper()
    static let label = "com.personalayer.macos.launchagent"

    private var plistURL: URL {
        FileManager.default
            .urls(for: .libraryDirectory, in: .userDomainMask)
            .first!
            .appendingPathComponent("LaunchAgents/\(Self.label).plist")
    }

    var isEnabled: Bool {
        FileManager.default.fileExists(atPath: plistURL.path)
    }

    func install(executablePath: String) throws {
        let plist: [String: Any] = [
            "Label": Self.label,
            "ProgramArguments": [executablePath],
            "RunAtLoad": true,
            "KeepAlive": false,
            "StandardOutPath": "~/Library/Logs/PersonalLayer/stdout.log",
            "StandardErrorPath": "~/Library/Logs/PersonalLayer/stderr.log"
        ]
        let data = try PropertyListSerialization.data(
            fromPropertyList: plist,
            format: .xml,
            options: 0
        )
        let logDir = plistURL.deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Logs/PersonalLayer")
        try? FileManager.default.createDirectory(
            at: logDir,
            withIntermediateDirectories: true
        )
        try? FileManager.default.createDirectory(
            at: plistURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try data.write(to: plistURL)
        try runLaunchctl(args: ["load", "-w", plistURL.path])
    }

    func uninstall() throws {
        guard isEnabled else { return }
        try? runLaunchctl(args: ["unload", "-w", plistURL.path])
        try? FileManager.default.removeItem(at: plistURL)
    }

    private func runLaunchctl(args: [String]) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = args
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw LaunchAgentError.launchctlFailed(status: process.terminationStatus)
        }
    }
}

enum LaunchAgentError: Error {
    case launchctlFailed(status: Int32)
}
