import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var server: LocalServer
    @EnvironmentObject var domainStore: DomainApprovalStore
    @State private var showDomainAlert = false
    @State private var pendingDomain = ""
    @State private var launchAgentEnabled = LaunchAgentHelper.shared.isEnabled

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "brain")
                    .font(.title2)
                Text("Personal Layer")
                    .font(.headline)
            }
            .padding(.bottom, 4)

            HStack {
                Circle()
                    .fill(server.isRunning ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(server.isRunning ? "Running on 127.0.0.1:7432" : "Stopped")
                    .font(.caption)
            }

            Toggle("Run on Login", isOn: Binding(
                get: { launchAgentEnabled },
                set: { newValue in
                    toggleLaunchAgent(enabled: newValue)
                }
            ))
            .font(.caption)

            Divider()

            Text("Approved Domains")
                .font(.caption)
                .foregroundStyle(.secondary)
            if domainStore.approvedDomains.isEmpty {
                Text("None")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(domainStore.approvedDomains), id: \.self) { domain in
                    HStack {
                        Text(domain)
                            .font(.caption)
                        Spacer()
                        Button("Revoke") {
                            domainStore.revoke(domain: domain)
                        }
                        .font(.caption2)
                        .buttonStyle(.borderless)
                    }
                }
            }

            Divider()

            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q")
        }
        .padding()
        .frame(width: 280)
        .alert("Approve Domain", isPresented: $showDomainAlert) {
            Button("Allow", role: .none) {
                domainStore.approve(domain: pendingDomain)
                pendingDomain = ""
            }
            Button("Deny", role: .cancel) {
                pendingDomain = ""
            }
        } message: {
            Text("Allow \(pendingDomain) to access your context bundle?")
        }
        .onReceive(domainStore.$approvalRequest) { request in
            if let domain = request {
                pendingDomain = domain
                showDomainAlert = true
            }
        }
    }

    private func toggleLaunchAgent(enabled: Bool) {
        do {
            if enabled {
                let executable = Bundle.main.executablePath!
                try LaunchAgentHelper.shared.install(executablePath: executable)
            } else {
                try LaunchAgentHelper.shared.uninstall()
            }
            launchAgentEnabled = enabled
        } catch {
            launchAgentEnabled = LaunchAgentHelper.shared.isEnabled
            NSLog("PersonalLayer: LaunchAgent toggle failed: \(error)")
        }
    }
}
