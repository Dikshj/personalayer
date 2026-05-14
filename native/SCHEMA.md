# Personal Layer v4 GRDB Schema

Both macOS and iOS share the identical schema via GRDB migrations.

## Tables

### raw_event
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| eventType | TEXT NOT NULL | e.g. "gmail_metadata", "page_view" |
| payload | TEXT NOT NULL | JSON string |
| createdAt | DATETIME | Default now |
| privacyFiltered | BOOLEAN | Default false |
| connectorType | TEXT | "gmail", "spotify", etc. |

### kg_node
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| entityId | TEXT UNIQUE | Stable identifier |
| entityType | TEXT | "raw_event", "profile_segment", "insight" |
| label | TEXT | Human-readable label |
| attributes | TEXT | JSON metadata |
| embedding | BLOB | 384-dim float32 (Core ML all-MiniLM-L6-v2) |
| tier | TEXT | HOT, WARM, COOL, COLD |
| signalStrength | REAL | 0.0–1.0, default 1.0 |
| lastAccessedAt | DATETIME | Default now |
| createdAt | DATETIME | Default now |
| updatedAt | DATETIME | Default now |

### kg_edge
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| sourceEntityId | TEXT | FK to kg_node.entityId |
| targetEntityId | TEXT | FK to kg_node.entityId |
| relationType | TEXT | e.g. "derived_from", "similar_to" |
| weight | REAL | Edge confidence 0.0–1.0 |
| evidence | TEXT | JSON array of evidence |
| createdAt | DATETIME | Default now |

### temporal_chain
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| chainType | TEXT | e.g. "hourly_window" |
| sequence | TEXT | JSON array of {entityId, timestamp} |
| startDate | DATETIME | Window start |
| endDate | DATETIME | Window end |
| createdAt | DATETIME | Default now |

### domain_approval
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| domain | TEXT UNIQUE | Approved web domain |
| isApproved | BOOLEAN | Default false |
| approvedAt | DATETIME | Default now |

### shared_bundle
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| userId | TEXT UNIQUE | Local user identifier |
| bundleJson | TEXT | JSON context bundle |
| updatedAt | DATETIME | Default now |

## Migrations

| Migration | Version | Description |
|-----------|---------|-------------|
| v1_raw_events | 1 | Initial raw event table |
| v2_kg_nodes | 2 | Knowledge graph nodes with embeddings |
| v3_kg_edges | 3 | Knowledge graph edges |
| v4_temporal_chains | 4 | Temporal pattern chains |
| v5_domain_approvals | 5 | Per-domain CORS approvals |
| v6_shared_bundles | 6 | Shared context bundles |

## Verification Commands

Run in Xcode console or REPL:
```swift
import GRDB
let db = GRDBDatabase.shared.dbPool
try db.read { db in
    try db.tableNames().sorted().forEach { print($0) }
}
```
