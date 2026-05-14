import SwiftUI

struct ConnectorsView: View {
    @StateObject private var manager = ConnectorManager()

    var body: some View {
        NavigationView {
            List(ConnectorType.allCases) { type in
                HStack {
                    VStack(alignment: .leading) {
                        Text(type.displayName)
                            .font(.headline)
                        Text(manager.isConnected(type) ? "Connected" : "Not connected")
                            .font(.caption)
                            .foregroundColor(manager.isConnected(type) ? .green : .secondary)
                    }
                    Spacer()
                    Button(manager.isConnected(type) ? "Reconnect" : "Connect") {
                        manager.connect(type)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .navigationTitle("Connectors")
        }
    }
}

extension ConnectorType: Identifiable {
    var id: String { rawValue }
}
