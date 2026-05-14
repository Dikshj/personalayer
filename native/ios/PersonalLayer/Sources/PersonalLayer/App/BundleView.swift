import SwiftUI

struct BundleView: View {
    @State private var bundleText = "Loading..."

    var body: some View {
        ScrollView {
            Text(bundleText)
                .font(.caption.monospaced())
                .padding()
        }
        .navigationTitle("Context Bundle")
        .task {
            do {
                let bundle = try GRDBDatabase.shared.loadSharedBundle()
                let data = try JSONSerialization.data(withJSONObject: bundle, options: .prettyPrinted)
                bundleText = String(data: data, encoding: .utf8) ?? "Invalid"
            } catch {
                bundleText = "Error: \(error.localizedDescription)"
            }
        }
    }
}
