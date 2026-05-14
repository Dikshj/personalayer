import SwiftUI
import UniformTypeIdentifiers

struct ExportView: View {
    @State private var showingShareSheet = false
    @State private var exportURL: URL?

    var body: some View {
        VStack(spacing: 20) {
            Text("Export your Personal Layer data as a JSON bundle.")
                .multilineTextAlignment(.center)
                .padding()

            Button("Export Data") {
                do {
                    let bundle = try GRDBDatabase.shared.loadSharedBundle()
                    let data = try JSONSerialization.data(withJSONObject: bundle)
                    let url = FileManager.default.temporaryDirectory
                        .appendingPathComponent("personal_layer_export.json")
                    try data.write(to: url)
                    exportURL = url
                    showingShareSheet = true
                } catch {
                    // handle
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Export")
        .sheet(isPresented: $showingShareSheet) {
            if let url = exportURL {
                ShareSheet(items: [url])
            }
        }
    }
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
