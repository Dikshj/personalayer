import Foundation

/// NSXPCConnection-based native messaging host for Safari WebExtension.
/// Bridges messages between the Safari extension and the local GRDB database.
@objc protocol SafariExtensionProtocol {
    func getBundle(reply: @escaping ([String: Any]) -> Void)
    func track(eventType: String, payload: [String: Any], reply: @escaping (Bool) -> Void)
}

final class SafariNativeMessagingHost: NSObject, SafariExtensionProtocol {
    static let shared = SafariNativeMessagingHost()
    private var listener: NSXPCListener?

    func start() {
        listener = NSXPCListener(machServiceName: "com.personalayer.macos.safari")
        listener?.delegate = self
        listener?.resume()
    }

    func getBundle(reply: @escaping ([String: Any]) -> Void) {
        do {
            let bundle = try GRDBDatabase.shared.loadSharedBundle()
            reply(bundle)
        } catch {
            reply(["error": error.localizedDescription])
        }
    }

    func track(eventType: String, payload: [String: Any], reply: @escaping (Bool) -> Void) {
        do {
            try GRDBDatabase.shared.insertRawEvent(type: eventType, payload: payload)
            reply(true)
        } catch {
            reply(false)
        }
    }
}

extension SafariNativeMessagingHost: NSXPCListenerDelegate {
    func listener(_ listener: NSXPCListener, shouldAcceptNewConnection newConnection: NSXPCConnection) -> Bool {
        newConnection.exportedInterface = NSXPCInterface(with: SafariExtensionProtocol.self)
        newConnection.exportedObject = self
        newConnection.resume()
        return true
    }
}
