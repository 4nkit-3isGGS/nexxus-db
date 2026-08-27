// =============================================================================
// Graph Schema & Constraints Definition
// -----------------------------------------------------------------------------
// Defines uniqueness constraints on stable entity IDs and creates search indexes
// on normalized attributes for fast lookup in Neo4j.
// =============================================================================

// ==========================================
// 1. UNIQUE CONSTRAINTS (Ensures no duplicate IDs)

// ==========================================
CREATE CONSTRAINT person_id_unique IF NOT EXISTS
FOR (p:Person) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT phone_id_unique IF NOT EXISTS
FOR (ph:Phone) REQUIRE ph.id IS UNIQUE;

CREATE CONSTRAINT location_id_unique IF NOT EXISTS
FOR (l:Location) REQUIRE l.id IS UNIQUE;

CREATE CONSTRAINT vehicle_id_unique IF NOT EXISTS
FOR (v:Vehicle) REQUIRE v.id IS UNIQUE;

CREATE CONSTRAINT organization_id_unique IF NOT EXISTS
FOR (o:Organization) REQUIRE o.id IS UNIQUE;

// ==========================================
// 2. INDEXES (Fast lookup by normalized search fields)
// ==========================================
CREATE INDEX person_normalized_name_idx IF NOT EXISTS
FOR (p:Person) ON (p.normalized_name);

CREATE INDEX phone_normalized_number_idx IF NOT EXISTS
FOR (ph:Phone) ON (ph.normalized_number);

CREATE INDEX location_normalized_name_idx IF NOT EXISTS
FOR (l:Location) ON (l.normalized_name);

CREATE INDEX vehicle_reg_idx IF NOT EXISTS
FOR (v:Vehicle) ON (v.registration_number);

CREATE INDEX org_normalized_name_idx IF NOT EXISTS
FOR (o:Organization) ON (o.normalized_name);
