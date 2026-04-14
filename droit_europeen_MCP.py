#!/usr/bin/env python3
"""Serveur MCP de requête aux APIs publiques EUR-Lex et CELLAR (droit européen)."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

# Charge .env depuis le répertoire du script, indépendamment du cwd
# d'où le MCP est lancé (p.ex. via `claude mcp add`).
load_dotenv(Path(__file__).resolve().parent / ".env")

from api_rest import CellarRestAPI
from api_sparql import CellarSparqlAPI
from api_soap import EurLexSoapAPI

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

mcp = FastMCP("EU Droit Européen MCP Server - EUR-Lex / CELLAR")

rest_api = CellarRestAPI()
sparql_api = CellarSparqlAPI()

_soap_api: Optional[EurLexSoapAPI] = None


def _get_soap() -> EurLexSoapAPI:
    global _soap_api
    if _soap_api is None:
        _soap_api = EurLexSoapAPI()
    return _soap_api


@mcp.tool()
def consulter_celex(
    celex_id: str,
    format: str = "html",
    language: str = "fra",
) -> Dict[str, Any]:
    """Récupère le contenu d'un document européen par son identifiant CELEX.

    Args:
        celex_id: Identifiant CELEX (ex: '32016R0679' pour le RGPD).
        format: 'html', 'xhtml', 'xml' ou 'pdf'.
        language: Code langue ISO 639-3 (fra, eng, deu...).
    """
    content = rest_api.get_content(celex_id, format=format, language=language)
    if format == "pdf":
        return {"celex": celex_id, "format": "pdf", "size_bytes": len(content)}
    return {"celex": celex_id, "format": format, "content": content.decode("utf-8", errors="replace")}


@mcp.tool()
def obtenir_metadonnees_celex(
    celex_id: str,
    notice: str = "object",
    language: str = "fra",
) -> Dict[str, Any]:
    """Récupère la notice de métadonnées XML d'un document CELEX.

    Args:
        celex_id: Identifiant CELEX.
        notice: 'object', 'branch', 'tree' ou 'identifiers'.
        language: Code langue ISO 639-3.
    """
    xml = rest_api.get_notice(celex_id, notice=notice, language=language)  # type: ignore[arg-type]
    return {"celex": celex_id, "notice": notice, "xml": xml}


@mcp.tool()
def executer_sparql(query: str) -> Dict[str, Any]:
    """Exécute une requête SPARQL brute contre l'endpoint CELLAR.

    Endpoint : http://publications.europa.eu/webapi/rdf/sparql
    """
    return sparql_api.query(query)


@mcp.tool()
def documents_lies(celex_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Liste les documents liés à un CELEX (modifications, consolidations, jurisprudence)."""
    return sparql_api.related_documents(celex_id, limit=limit)


@mcp.tool()
def rechercher_eurlex(
    expert_query: str,
    page: int = 1,
    page_size: int = 10,
    search_language: str = "fr",
) -> Any:
    """Recherche experte plein-texte via le webservice SOAP EUR-Lex.

    ⚠️ Syntaxe EUR-Lex expert query — PROPRIÉTAIRE, pas du SQL.
    Les champs sont TOUJOURS en MAJUSCULES. N'utilise JAMAIS CONTAINS, LIKE, WHERE.

    Champs principaux :
      DN : Document Number (CELEX) — ex: DN = 32016R0679
      TI : Title (titre)           — ex: TI ~ "données personnelles"
      TE : Text (texte intégral)   — ex: TE ~ "cybersécurité"
      FM : Form (type d'acte)      — ex: FM = reg | dir | dec | deccfsp
      AU : Author                  — ex: AU = commission | council | europarl
      DD : Document Date           — ex: DD >= 2020-01-01
      DC : Date of effect          — ex: DC >= 2018-05-25
      CT : Court (jurisprudence)   — ex: CT = CJEU
      CASE : Case number (CJUE)    — ex: CASE = C-131/12

    Opérateurs :
      `=`            égalité exacte (CELEX, type, auteur…)
      `~`            contient / fuzzy (champs texte comme TI, TE)
      `<`, `>`, `<=`, `>=`  comparaison (dates, numéros)
      `AND`, `OR`, `NOT`    combinaisons booléennes
      `"..."`        guillemets pour les phrases multi-mots

    Exemples concrets (à adapter) :
      • `DN = 32016R0679`
          → le RGPD par son identifiant CELEX
      • `TI ~ "intelligence artificielle" AND FM = reg`
          → règlements avec "intelligence artificielle" dans le titre
      • `AU = commission AND DD >= 2024-01-01 AND FM = dec`
          → décisions de la Commission adoptées depuis 2024
      • `TE ~ "cryptoactifs" AND FM = reg AND DD >= 2020-01-01`
          → règlements mentionnant "cryptoactifs" dans le texte depuis 2020
      • `CT = CJEU AND TI ~ "protection des données"`
          → arrêts CJUE sur la protection des données

    Limite : depuis le 1ᵉʳ janvier 2026, max 10 000 résultats par requête.
    Nécessite EURLEX_USERNAME et EURLEX_PASSWORD dans l'environnement.
    Doc de référence : https://eur-lex.europa.eu/content/help/eurlex-content/expert-search.html

    Args:
        expert_query: la requête en syntaxe EUR-Lex experte (voir exemples ci-dessus).
        page: numéro de page (1 par défaut).
        page_size: résultats par page (10 par défaut, max 100).
        search_language: code langue 2 lettres (fr, en, de, it, es…).

    Returns:
        dict avec num_hits, total_hits, page, language, results (liste de
        {reference, rank, title, document_links}).
    """
    return _get_soap().search(
        expert_query=expert_query,
        page=page,
        page_size=page_size,
        search_language=search_language,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
