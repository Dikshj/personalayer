import SwiftUI

struct ConnectorsView: View {
    @StateObject private var connectors = ConnectorManager()

    var body: some View {
        List(ConnectorType.allCases, id: \.self) { type in
            HStack {
                Text(type.displayName)
                Spacer()
                if connectors.isConnected(type) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Button("Connect") {
                        connectors.connect(type)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                }
            }
        }
        .navigationTitle("Connectors")
    }
}
