"""Smoke test : appelle REST et SPARQL contre EUR-Lex/CELLAR (sans auth)."""

import sys
from api_rest import CellarRestAPI
from api_sparql import CellarSparqlAPI

RGPD_CELEX = "32016R0679"


def test_rest_content():
    api = CellarRestAPI()
    try:
        content = api.get_content(RGPD_CELEX, format="html", language="fra")
        assert len(content) > 1000, f"Contenu trop court : {len(content)} octets"
        print(f"[REST] get_content RGPD → OK ({len(content)} octets HTML)")
    finally:
        api.close()


def test_rest_notice():
    api = CellarRestAPI()
    try:
        xml = api.get_notice(RGPD_CELEX, notice="object")
        assert "<" in xml and len(xml) > 500, "XML incomplet"
        print(f"[REST] get_notice RGPD → OK ({len(xml)} caractères XML)")
    finally:
        api.close()


def test_sparql_trivial():
    api = CellarSparqlAPI()
    try:
        result = api.query("SELECT * WHERE { ?s ?p ?o } LIMIT 3")
        bindings = result.get("results", {}).get("bindings", [])
        assert len(bindings) > 0, "Aucun résultat SPARQL"
        print(f"[SPARQL] requête triviale → OK ({len(bindings)} bindings)")
    finally:
        api.close()


def test_sparql_related():
    api = CellarSparqlAPI()
    try:
        related = api.related_documents(RGPD_CELEX, limit=5)
        print(f"[SPARQL] related_documents RGPD → {len(related)} liens")
    finally:
        api.close()


if __name__ == "__main__":
    failures = 0
    for fn in [test_rest_content, test_rest_notice, test_sparql_trivial, test_sparql_related]:
        try:
            fn()
        except Exception as e:
            failures += 1
            print(f"[FAIL] {fn.__name__}: {type(e).__name__}: {e}")
    sys.exit(1 if failures else 0)
