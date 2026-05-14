import SwiftUI

struct DomainApprovalView: View {
    @StateObject private var store = DomainApprovalStore()
    @State private var newDomain = ""

    var body: some View {
        NavigationView {
            List {
                Section("Add Domain") {
                    HStack {
                        TextField("example.com", text: $newDomain)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                        Button("Approve") {
                            if !newDomain.isEmpty {
                                store.approve(domain: newDomain)
                                newDomain = ""
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }

                Section("Approved Domains") {
                    if store.approvedDomains.isEmpty {
                        Text("No domains approved yet")
                            .foregroundColor(.secondary)
                    } else {
                        ForEach(Array(store.approvedDomains), id: \.self) { domain in
                            HStack {
                                Text(domain)
                                Spacer()
                                Button("Revoke") {
                                    store.revoke(domain: domain)
                                }
                                .foregroundColor(.red)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Web Permissions")
        }
    }
}
