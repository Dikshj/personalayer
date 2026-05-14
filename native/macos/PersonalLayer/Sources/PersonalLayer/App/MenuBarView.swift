import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var server: LocalServer
    @EnvironmentObject var domainStore: DomainApprovalStore
    @State private var showingApprovalAlert = false
    @State private var pendingDomain = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Status
            HStack {
                Image(systemName: server.isRunning ? "brain.head.profile.fill" : "brain.head.profile")
                    .foregroundColor(server.isRunning ? .green : .red)
                Text(server.isRunning ? "Personal Layer Active" : "Personal Layer Stopped")
                    .font(.headline)
            }

            Divider()

            // Approved Domains
            if !domainStore.approvedDomains.isEmpty {
                Text("Approved Domains")
                    .font(.caption)
                    .foregroundColor(.secondary)
                ForEach(Array(domainStore.approvedDomains).sorted(), id: \.self) { domain in
                    HStack {
                        Text(domain)
                            .font(.body)
                        Spacer()
                        Button("Revoke") {
                            domainStore.revoke(domain: domain)
                        }
                        .buttonStyle(.plain)
                        .foregroundColor(.red)
                    }
                }
            } else {
                Text("No domains approved")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Divider()

            // Pending approval alert
            if let request = domainStore.approvalRequest {
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(Image(systemName: "exclamationmark.triangle")) Domain Approval Request")
                        .font(.subheadline.bold())
                    Text("\(request) wants to access your Personal Layer")
                        .font(.caption)
                    HStack {
                        Button("Deny") {
                            domainStore.approvalRequest = nil
                        }
                        .buttonStyle(.bordered)
                        Button("Approve") {
                            domainStore.approve(domain: request)
                            domainStore.approvalRequest = nil
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding(8)
                .background(Color.yellow.opacity(0.1))
                .cornerRadius(8)
            }

            Divider()

            // LaunchAgent
            LaunchAgentToggle()

            Divider()

            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q")
        }
        .padding()
        .frame(width: 320)
    }
}

struct LaunchAgentToggle: View {
    @State private var isEnabled = false

    var body: some View {
        Toggle("Run on Login", isOn: $isEnabled)
            .onChange(of: isEnabled) { newValue in
                if newValue {
                    LaunchAgentHelper.install()
                } else {
                    LaunchAgentHelper.uninstall()
                }
            }
            .onAppear {
                isEnabled = LaunchAgentHelper.isInstalled()
            }
    }
}
