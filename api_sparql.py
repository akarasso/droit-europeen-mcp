"""Client SPARQL CELLAR — requêtes relationnelles sur le graphe RDF EU Publications Office."""

from typing import Any, Dict, List
import httpx

SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"


class CellarSparqlAPI:
    def __init__(self, timeout: float = 60.0):
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def query(self, sparql: str) -> Dict[str, Any]:
        """Exécute une requête SPARQL brute et renvoie le résultat JSON standard."""
        r = self._client.post(
            SPARQL_ENDPOINT,
            data={"query": sparql, "format": "application/sparql-results+json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        r.raise_for_status()
        return r.json()

    def bindings(self, sparql: str) -> List[Dict[str, Any]]:
        """Raccourci : renvoie directement la liste de bindings de résultats."""
        return self.query(sparql).get("results", {}).get("bindings", [])

    def related_documents(self, celex: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Documents liés à un CELEX (modifications, consolidations, jurisprudence)."""
        sparql = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT DISTINCT ?related ?relation WHERE {{
            ?work cdm:resource_legal_id_celex "{celex}"^^<http://www.w3.org/2001/XMLSchema#string> .
            {{ ?work ?relation ?related . }}
            UNION
            {{ ?related ?relation ?work . }}
            FILTER(STRSTARTS(STR(?relation), "http://publications.europa.eu/ontology/cdm#"))
        }}
        LIMIT {limit}
        """
        return self.bindings(sparql)
