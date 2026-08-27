"""
Neo4j Database Driver & Connection Manager
------------------------------------------
Handles connection pooling, session lifecycle, health check verification,
and parameterized Cypher query execution for the Criminal Network Intelligence System.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

load_dotenv()


NEO4J_URL = os.getenv("NEO4J_URL", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "passwordisneo4j")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


class Neo4jConnection:
    """Manages connection lifecycle with Neo4j database."""

    def __init__(self, url: str = NEO4J_URL, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.url = url
        self.user = user
        self.password = password
        self.driver: Driver | None = None

    def connect(self) -> Driver:
        if self.driver is None:
            self.driver = GraphDatabase.driver(self.url, auth=(self.user, self.password))
        return self.driver

    def close(self):
        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def verify_connectivity(self) -> bool:
        """Verifies if database is reachable."""
        try:
            driver = self.connect()
            driver.verify_connectivity()
            return True
        except Exception as e:
            print(f"[Neo4j Error] Connection failed: {e}")
            return False

    def query(self, cypher_query: str, parameters: dict | None = None, db: str = NEO4J_DATABASE):
        """Execute a read/write Cypher query and return list of records as dicts."""
        driver = self.connect()
        with driver.session(database=db) as session:
            result = session.run(cypher_query, parameters or {})
            return [record.data() for record in result]


# Global singleton instance
db = Neo4jConnection()
