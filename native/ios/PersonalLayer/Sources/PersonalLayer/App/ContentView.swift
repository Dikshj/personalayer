import SwiftUI

struct ContentView: View {
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    var body: some View {
        Group {
            if hasCompletedOnboarding {
                MainTabView()
            } else {
                OnboardingView()
            }
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            BundleView()
                .tabItem { Label("Context", systemImage: "brain") }
            ConnectorsView()
                .tabItem { Label("Connectors", systemImage: "link") }
            DomainApprovalView()
                .tabItem { Label("Permissions", systemImage: "checkmark.shield") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gear") }
        }
    }
}
