import Cocoa
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate, ObservableObject {
    let server = LocalServer()
    let domainStore = DomainApprovalStore()
    private var statusItem: NSStatusItem?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        do {
            try server.start()
            try domainStore.migrate()
            RefreshScheduler.shared.register()
            RefreshScheduler.shared.schedule()
            NativeMessagingHost.shared.start()
        } catch {
            NSLog("PersonalLayer startup error: \(error)")
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        server.stop()
        NativeMessagingHost.shared.stop()
    }
}
