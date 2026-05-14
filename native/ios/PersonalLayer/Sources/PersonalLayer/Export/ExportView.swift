import SwiftUI

struct ExportView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var exportData: String = ""
    @State private var isLoading = false

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                Text("Export Your Data")
                    .font(.title2.bold())
                Text("This exports your knowledge graph nodes, edges, and context bundles as JSON. Raw events are excluded.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)

                if isLoading {
                    ProgressView("Generating export...")
                } else if !exportData.isEmpty {
                    TextEditor(text: $exportData)
                        .font(.system(.caption, design: .monospaced))
                        .border(Color.secondary.opacity(0.2))

                    ShareLink(item: exportData) {
                        Label("Share Export", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.borderedProminent)
                }

                Button("Generate Export") {
                    Task { await generateExport() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isLoading)

                Spacer()
            }
            .padding()
            .navigationBarItems(trailing: Button("Done") { dismiss() })
        }
    }

    private func generateExport() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let bundle = try GRDBDatabase.shared.loadSharedBundle()
            let nodes = try GRDBDatabase.shared.nodesByTier(.hot, limit: 100)
            let export: [String: Any] = [
                "version": "v4",
                "exported_at": ISO8601DateFormatter().string(from: Date()),
                "bundle": bundle,
                "nodes": nodes.map { ["id": $0.entityId, "label": $0.label, "type": $0.entityType, "tier": $0.tier] }
            ]
            exportData = String(data: try JSONSerialization.data(withJSONObject: export, options: .prettyPrinted), encoding: .utf8) ?? "{}"
        } catch {
            exportData = "{\"error\": \"\(error.localizedDescription)\"}"
        }
    }
}
