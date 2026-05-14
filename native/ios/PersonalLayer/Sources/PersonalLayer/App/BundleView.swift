import SwiftUI

struct BundleView: View {
    @State private var bundle: [String: Any] = [:]
    @State private var isLoading = false

    var body: some View {
        NavigationView {
            List {
                if let hot = bundle["hot_context"] as? [[String: Any]], !hot.isEmpty {
                    Section("Hot Context") {
                        ForEach(hot.indices, id: \.self) { i in
                            ContextNodeRow(node: hot[i])
                        }
                    }
                }
                if let warm = bundle["warm_context"] as? [[String: Any]], !warm.isEmpty {
                    Section("Warm Context") {
                        ForEach(warm.indices, id: \.self) { i in
                            ContextNodeRow(node: warm[i])
                        }
                    }
                }
                if let insight = bundle["daily_insight"] as? String {
                    Section("Daily Insight") {
                        Text(insight)
                            .font(.body)
                    }
                }
            }
            .navigationTitle("Your Context")
            .refreshable { await loadBundle() }
            .onAppear { Task { await loadBundle() } }
        }
    }

    private func loadBundle() async {
        isLoading = true
        defer { isLoading = false }
        do {
            bundle = try GRDBDatabase.shared.loadSharedBundle()
        } catch {
            bundle = [:]
        }
    }
}

struct ContextNodeRow: View {
    let node: [String: Any]

    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(node["label"] as? String ?? "Unknown")
                    .font(.headline)
                Text(node["id"] as? String ?? "")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if let strength = node["strength"] as? Double {
                Text(String(format: "%.2f", strength))
                    .font(.caption.monospaced())
                    .foregroundColor(strengthColor(strength))
            }
        }
    }

    private func strengthColor(_ s: Double) -> Color {
        if s > 0.7 { return .green }
        if s > 0.3 { return .orange }
        return .red
    }
}
