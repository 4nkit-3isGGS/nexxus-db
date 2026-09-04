"""
CLI Runner for Ingesting NLP Payload into Neo4j
"""
import json
import os
import sys

from backend.app.neo4j_driver import db
from backend.app.ingestion.graph_ingestor import ingest_nlp_payload


def run():
    contract_file = "output_contract.JSON"
    if not os.path.exists(contract_file):
        print(f"Error: {contract_file} not found.")
        sys.exit(1)

    print(f"[*] Reading payload from {contract_file}...")
    with open(contract_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    print("[*] Connecting to Neo4j...")
    if not db.verify_connectivity():
        print("[!] Failed to connect to Neo4j. Ensure Neo4j is running.")
        sys.exit(1)
    print("[+] Connected to Neo4j.")

    # Clean up any null nodes and previous partial run nodes
    db.query("MATCH (p:Person) WHERE p.id IS NULL DETACH DELETE p")
    db.query("MATCH (p:Person) WHERE p.id STARTS WITH 'P-' AND NOT p.name = 'Test Suspect One' DETACH DELETE p")

    print(f"[*] Starting ingestion of {len(payload.get('entities', []))} entities and {len(payload.get('relationships', []))} relationships...")
    
    result = ingest_nlp_payload(payload)

    print("\n" + "=" * 50)
    print("           INGESTION RESULTS")
    print("=" * 50)
    for key, value in result.items():
        print(f"  {key.replace('_', ' ').capitalize()}: {value}")
    print("=" * 50)

    # Verify directly in Neo4j
    print("\n[*] Verifying Neo4j Database Totals:")
    node_counts = db.query("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC")
    print("  Node counts:")
    for row in node_counts:
        print(f"    - {row['label']}: {row['count']}")

    rel_counts = db.query("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC")
    print("  Relationship counts:")
    for row in rel_counts:
        print(f"    - {row['rel_type']}: {row['count']}")

    duplicate_flags = db.query("MATCH (e1)-[r:POSSIBLE_DUPLICATE]->(e2) RETURN coalesce(e1.name, e1.id) AS entity1, coalesce(e2.name, e2.id) AS entity2, r.confidence_score AS score, r.reason AS reason")
    if duplicate_flags:
        print(f"\n[!] Entity Resolution Review Queue ({len(duplicate_flags)} flagged):")
        for f in duplicate_flags:
            print(f"    - [{f['score']:.2f}] {f['entity1']} <---> {f['entity2']} ({f['reason']})")
    
    db.close()
    print("\n[+] Ingestion and verification complete!")


if __name__ == "__main__":
    run()
