import GRDB
import Combine

final class DomainApprovalStore: ObservableObject {
    @Published var approvedDomains: Set<String> = []

    private let dbPool: DatabasePool

    init(dbPool: DatabasePool? = nil) {
        if let pool = dbPool { self.dbPool = pool } else {
            let fm = FileManager.default
            let appSupport = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            let dir = appSupport.appendingPathComponent("PersonalLayer", isDirectory: true)
            try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
            self.dbPool = try! DatabasePool(path: dir.appendingPathComponent("personal_layer.sqlite").path)
        }
    }

    func migrate() throws {
        var migrator = DatabaseMigrator()
        migrator.registerMigration("approval_v1") { db in
            try db.create(table: "domain_approvals", ifNotExists: true) { t in
                t.column("domain", .text).primaryKey()
                t.column("approved_at", .datetime).notNull()
            }
        }
        try migrator.migrate(dbPool)
        reload()
    }

    func isApproved(domain: String) -> Bool { approvedDomains.contains(domain) }
    func approve(domain: String) {
        try? dbPool.write { db in try DomainApproval(domain: domain, approvedAt: Date()).upsert(db) }
        reload()
    }
    func revoke(domain: String) {
        try? dbPool.write { db in _ = try DomainApproval.deleteOne(db, key: ["domain": domain]) }
        reload()
    }
    private func reload() {
        let domains = (try? dbPool.read { db in try DomainApproval.fetchAll(db).map(\.domain) }) ?? []
        approvedDomains = Set(domains)
    }
}
