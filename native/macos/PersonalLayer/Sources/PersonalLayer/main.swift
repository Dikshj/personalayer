import SwiftUI

@main
struct PersonalLayerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        MenuBarExtra("Personal Layer", systemImage: "brain") {
            MenuBarView()
                .environmentObject(appDelegate.server)
                .environmentObject(appDelegate.domainStore)
        }
        .menuBarExtraStyle(.window)
    }
}
