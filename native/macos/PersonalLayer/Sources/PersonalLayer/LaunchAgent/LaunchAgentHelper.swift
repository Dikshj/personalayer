import Foundation

final class LaunchAgentHelper {
    static let label = "com.personalayer.macos.launchagent"
    static var plistPath: String {
        "\(NSHomeDirectory())/Library/LaunchAgents/\(label).plist"
    }

    static func install() {
        let plist = """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>\(label)</string>
            <key>ProgramArguments</key>
            <array>
                <string>\(Bundle.main.executablePath ?? "/usr/bin/true")</string>
            </array>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
        </dict>
        </plist>
        """
        try? plist.write(toFile: plistPath, atomically: true, encoding: .utf8)
        Process.launchedProcess(launchPath: "/bin/launchctl", arguments: ["load", plistPath])
    }

    static func uninstall() {
        Process.launchedProcess(launchPath: "/bin/launchctl", arguments: ["unload", plistPath])
        try? FileManager.default.removeItem(atPath: plistPath)
    }

    static func isInstalled() -> Bool {
        FileManager.default.fileExists(atPath: plistPath)
    }
}
