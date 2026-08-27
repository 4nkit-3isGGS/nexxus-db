// =============================================================================
// Seed / Synthetic Criminal Network Dataset
// -----------------------------------------------------------------------------
// Populates sample criminal network entities (Person, Phone, Location,
// Vehicle, Organization) and relationships (CALLED, TRANSACTED_WITH, PRESENT_AT,
// OWNS_VEHICLE, MEMBER_OF) with timestamps, source provenance, and confidence.
// =============================================================================

// ==========================================
// 1. PERSON NODES

// ==========================================
MERGE (p1:Person {id: "P001"})
SET p1.name = "Rahul Sharma",
    p1.normalized_name = "rahul sharma",
    p1.aliases = ["R. Sharma", "Rahul Pandit"],
    p1.created_at = "2026-08-20T10:00:00Z",
    p1.updated_at = "2026-08-20T10:00:00Z";

MERGE (p2:Person {id: "P002"})
SET p2.name = "Sameer Khan",
    p2.normalized_name = "sameer khan",
    p2.aliases = ["Sam", "SK"],
    p2.created_at = "2026-08-20T10:00:00Z",
    p2.updated_at = "2026-08-20T10:00:00Z";

MERGE (p3:Person {id: "P003"})
SET p3.name = "Vikram Malhotra",
    p3.normalized_name = "vikram malhotra",
    p3.aliases = ["Vicky", "Boss"],
    p3.created_at = "2026-08-20T10:00:00Z",
    p3.updated_at = "2026-08-20T10:00:00Z";

MERGE (p4:Person {id: "P004"})
SET p4.name = "Amit Verma",
    p4.normalized_name = "amit verma",
    p4.aliases = ["Chintu"],
    p4.created_at = "2026-08-20T10:00:00Z",
    p4.updated_at = "2026-08-20T10:00:00Z";

// ==========================================
// 2. OTHER ENTITY NODES (Phone, Location, Vehicle, Organization)
// ==========================================
MERGE (ph1:Phone {id: "PH001"})
SET ph1.number = "+919876543210",
    ph1.normalized_number = "9876543210";

MERGE (ph2:Phone {id: "PH002"})
SET ph2.number = "+919123456789",
    ph2.normalized_number = "9123456789";

MERGE (loc1:Location {id: "LOC001"})
SET loc1.name = "Old Delhi Warehouse",
    loc1.normalized_name = "old delhi warehouse",
    loc1.latitude = 28.6562,
    loc1.longitude = 77.2410;

MERGE (loc2:Location {id: "LOC002"})
SET loc2.name = "Connaught Place",
    loc2.normalized_name = "connaught place",
    loc2.latitude = 28.6315,
    loc2.longitude = 77.2167;

MERGE (v1:Vehicle {id: "VEH001"})
SET v1.registration_number = "DL01AB1234",
    v1.vehicle_type = "Sedan (Black SUV)";

MERGE (org1:Organization {id: "ORG001"})
SET org1.name = "Shadow Logistics Pvt Ltd",
    org1.normalized_name = "shadow logistics pvt ltd";

// ==========================================
// 3. RELATIONSHIPS & EVIDENCE
// ==========================================

// Rahul called Sameer
MERGE (p1)-[r1:CALLED {source_doc: "CDR_AUG_01"}]->(p2)
SET r1.timestamp = "2026-08-20T14:32:00Z",
    r1.duration = 180,
    r1.confidence = 0.98;

// Sameer called Vikram
MERGE (p2)-[r2:CALLED {source_doc: "CDR_AUG_02"}]->(p3)
SET r2.timestamp = "2026-08-20T15:10:00Z",
    r2.duration = 420,
    r2.confidence = 0.95;

// Rahul sent money to Vikram (Hawala transfer)
MERGE (p1)-[r3:TRANSACTED_WITH {source_doc: "FIN_INTEL_88"}]->(p3)
SET r3.timestamp = "2026-08-21T09:15:00Z",
    r3.amount = 500000,
    r3.transaction_id = "TXN_99824",
    r3.confidence = 0.92;

// Rahul was present at Old Delhi Warehouse
MERGE (p1)-[r4:PRESENT_AT {source_doc: "FIR_102"}]->(loc1)
SET r4.timestamp = "2026-08-21T18:00:00Z",
    r4.confidence = 0.90;

// Sameer was also present at Old Delhi Warehouse (Shared Location Co-occurrence!)
MERGE (p2)-[r5:PRESENT_AT {source_doc: "FIR_102"}]->(loc1)
SET r5.timestamp = "2026-08-21T18:30:00Z",
    r5.confidence = 0.88;

// Amit owns the getaway vehicle
MERGE (p4)-[r6:OWNS_VEHICLE {source_doc: "RTO_RECORD"}]->(v1)
SET r6.confidence = 0.99,
    r6.timestamp = "2024-05-12T00:00:00Z";

// Amit called Rahul
MERGE (p4)-[r7:CALLED {source_doc: "CDR_AUG_03"}]->(p1)
SET r7.timestamp = "2026-08-21T17:45:00Z",
    r7.duration = 60,
    r7.confidence = 0.97;

// Vikram is the director of Shadow Logistics
MERGE (p3)-[r8:MEMBER_OF {source_doc: "MCA_RECORDS"}]->(org1)
SET r8.role = "Director",
    r8.confidence = 0.99,
    r8.timestamp = "2021-01-10T00:00:00Z";
