import SwiftUI

struct ContentView: View {
    @EnvironmentObject var refreshScheduler: RefreshScheduler
    @EnvironmentObject var domainStore: DomainApprovalStore
    @State private var showingExportSheet = false

    var body: some View {
        NavigationStack {
            List {
                Section("Status") {
                    HStack {
                        Circle()
                            .fill(refreshScheduler.isRunning ? Color.green : Color.orange)
                            .frame(width: 10, height: 10)
                        Text(refreshScheduler.isRunning ? "Refreshing..." : "Idle")
                    }
                    Text("Next refresh: \(refreshScheduler.nextRefreshFormatted)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section("Profile") {
                    NavigationLink("View Bundle") {
                        BundleView()
                    }
                    NavigationLink("Connectors") {
                        ConnectorsView()
                    }
                }

                Section("Privacy") {
                    NavigationLink("Approved Domains") {
                        DomainApprovalView()
                    }
                    NavigationLink("Export Data") {
                        ExportView()
                    }
                    NavigationLink("Delete Account") {
                        DeleteAccountView()
                    }
                }
            }
            .navigationTitle("Personal Layer")
        }
    }
}
