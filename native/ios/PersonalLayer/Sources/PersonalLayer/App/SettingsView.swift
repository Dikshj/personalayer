import SwiftUI

struct SettingsView: View {
    @State private var showingExport = false
    @State private var showingDelete = false

    var body: some View {
        NavigationView {
            List {
                Section("Data") {
                    Button("Export My Data") { showingExport = true }
                    Button("Delete My Account", role: .destructive) { showingDelete = true }
                }
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("0.1.0")
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("Architecture")
                        Spacer()
                        Text("v4")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .sheet(isPresented: $showingExport) { ExportView() }
            .sheet(isPresented: $showingDelete) { DeleteAccountView() }
        }
    }
}
