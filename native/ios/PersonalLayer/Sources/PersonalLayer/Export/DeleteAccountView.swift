import SwiftUI

struct DeleteAccountView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var confirmationText = ""
    @State private var isDeleting = false
    @State private var showConfirmation = false

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.red)

                Text("Delete All Data")
                    .font(.title2.bold())

                Text("This will permanently delete all locally stored data including your knowledge graph, context bundles, and raw events. This action cannot be undone.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Type DELETE to confirm:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    TextField("DELETE", text: $confirmationText)
                        .textFieldStyle(.roundedBorder)
                        .autocapitalization(.allCharacters)
                }

                Button("Permanently Delete") {
                    isDeleting = true
                    Task {
                        await deleteAllData()
                        isDeleting = false
                        showConfirmation = true
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
                .disabled(confirmationText != "DELETE" || isDeleting)

                Spacer()
            }
            .padding()
            .navigationBarItems(trailing: Button("Cancel") { dismiss() })
            .alert("Data Deleted", isPresented: $showConfirmation) {
                Button("OK", role: .cancel) { dismiss() }
            } message: {
                Text("All local data has been deleted.")
            }
        }
    }

    private func deleteAllData() async {
        let fm = FileManager.default
        let appSupport = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("PersonalLayer")
        try? fm.removeItem(at: dir)

        // Also clear UserDefaults cursors
        for key in ["gmail", "spotify", "calendar", "notion", "youtube"] {
            ConnectorCursorStore.clear(for: key)
        }
    }
}
