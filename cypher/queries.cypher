// ==========================================================
// USEFUL INVESTIGATION CYPHER QUERIES
// ==========================================================

// 1. Get complete profile and 1-hop connections of a suspect (e.g. Rahul Sharma)
MATCH (p:Person {id: "P001"})-[r]-(target)
RETURN p.name AS suspect, type(r) AS relationship, target.name AS connected_entity, properties(r) AS details;

// 2. Co-occurrence: Find persons who were present at the same location
MATCH (p1:Person)-[:PRESENT_AT]->(loc:Location)<-[:PRESENT_AT]-(p2:Person)
WHERE p1.id < p2.id
RETURN p1.name AS Suspect_1, p2.name AS Suspect_2, loc.name AS Location;

// 3. Multi-hop traversal: Uncover hidden connections (up to 3 hops away from Rahul)
MATCH path = (p:Person {id: "P001"})-[*1..3]-(connected)
RETURN path;

// 4. Shortest Path: Find the direct or indirect chain connecting two suspects (e.g. Amit to Vikram)
MATCH path = shortestPath((p1:Person {id: "P004"})-[*]-(p2:Person {id: "P003"}))
RETURN path;

// 5. High-Value Financial Transactions (> 100,000 INR)
MATCH (sender:Person)-[t:TRANSACTED_WITH]->(receiver:Person)
WHERE t.amount >= 100000
RETURN sender.name AS Sender, receiver.name AS Receiver, t.amount AS Amount, t.transaction_id AS Txn_ID, t.source_doc AS Provenance;

// 6. Organization Affiliation & Corporate Fronts
MATCH (p:Person)-[m:MEMBER_OF]->(o:Organization)
RETURN p.name AS Leader, m.role AS Role, o.name AS Organization;

// 7. Graph Statistics (Total counts for dashboard)
MATCH (n)
RETURN labels(n)[0] AS Entity_Type, count(n) AS Total_Count;
