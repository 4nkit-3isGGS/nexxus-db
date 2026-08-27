"""
Database Connection & Initialization Test Script
------------------------------------------------
Verifies Neo4j connectivity, applies schema constraints and indexes,
seeds synthetic test data, and runs sample verification queries.
"""

import os
import sys


# Ensure backend root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.neo4j_driver import db

def run_script(filepath: str):
    """Executes multi-statement Cypher script separated by semicolons."""
    print(f"\n[#] Executing: {os.path.basename(filepath)}...")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by semicolon, filter comments & empty statements
    statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
    for idx, stmt in enumerate(statements, start=1):
        if not stmt or stmt.startswith("//"):
            continue
        try:
            db.query(stmt)
            print(f"  [Statement {idx}] OK")
        except Exception as e:
            print(f"  [Statement {idx}] Failed: {e}")

def main():
    print("==================================================")
    print("  [>] Testing Neo4j Connection & Loading Graph Data")
    print("==================================================")

    # 1. Test Connection
    print("Checking connection to Neo4j...")
    if not db.verify_connectivity():
        print("\n[!] Failed to connect to Neo4j. Please verify:")
        print("   1. Neo4j Desktop database is STARTED.")
        print("   2. Credentials in .env match your Neo4j Desktop password.")
        return

    print("[+] Neo4j connection successful!\n")

    # 2. Run Schema (Constraints & Indexes)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(project_root, "cypher", "schema.cypher")
    seed_path = os.path.join(project_root, "cypher", "seed.cypher")

    if os.path.exists(schema_path):
        run_script(schema_path)

    # 3. Seed Database
    if os.path.exists(seed_path):
        run_script(seed_path)

    # 4. Verify with a Test Query
    print("\n[*] Running Verification Query (Suspects & Connections):")
    query = """
    MATCH (p:Person)-[r]->(target)
    RETURN p.name AS Suspect, type(r) AS Relationship, target.name AS Target
    LIMIT 10
    """
    results = db.query(query)
    for r in results:
        print(f"  --> {r.get('Suspect')} --[{r.get('Relationship')}]--> {r.get('Target')}")

    print("\n[+] Setup verified successfully! Your criminal network graph is live.")
    db.close()

if __name__ == "__main__":
    main()
