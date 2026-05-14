import SwiftUI

struct DomainApprovalView: View {
    @EnvironmentObject var store: DomainApprovalStore

    var body: some View {
        List {
            if store.approvedDomains.isEmpty {
                Text("No approved domains")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(store.approvedDomains), id: \.self) { domain in
                    HStack {
                        Text(domain)
                        Spacer()
                        Button("Revoke") {
                            store.revoke(domain: domain)
                        }
                        .foregroundStyle(.red)
                    }
                }
            }
        }
        .navigationTitle("Approved Domains")
    }
}
