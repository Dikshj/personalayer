import SwiftUI

@main
struct PersonalLayerApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appDelegate.refreshScheduler)
                .environmentObject(appDelegate.domainStore)
        }
    }
}
