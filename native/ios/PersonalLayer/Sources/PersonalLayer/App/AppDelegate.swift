import UIKit
import BackgroundTasks

final class AppDelegate: NSObject, UIApplicationDelegate, ObservableObject {
    let refreshScheduler = RefreshScheduler()
    let domainStore = DomainApprovalStore()

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        refreshScheduler.register()
        refreshScheduler.schedule()
        try? domainStore.migrate()
        return true
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        refreshScheduler.schedule()
    }
}
