import SwiftUI

struct DeleteAccountView: View {
    @State private var confirmText = ""
    @State private var showAlert = false

    var body: some View {
        VStack(spacing: 20) {
            Text("Deleting your account will permanently remove all local data, including your profile, memory tiers, and raw events.")
                .foregroundStyle(.red)
                .multilineTextAlignment(.center)
                .padding()

            TextField("Type DELETE to confirm", text: $confirmText)
                .textFieldStyle(.roundedBorder)
                .autocorrectionDisabled()
                .padding(.horizontal)

            Button("Delete All Data") {
                if confirmText == "DELETE" {
                    do {
                        try GRDBDatabase.shared.wipeAllData()
                        showAlert = true
                    } catch {}
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(.red)
            .disabled(confirmText != "DELETE")
        }
        .navigationTitle("Delete Account")
        .alert("Data Deleted", isPresented: $showAlert) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("All local data has been removed.")
        }
    }
}
