"""Client SOAP EUR-Lex — recherche experte plein-texte (nécessite EU Login).

Note d'implémentation : nous n'utilisons PAS zeep malgré le fait qu'il soit le
client SOAP Python standard. zeep hang indéfiniment sur la réponse chunked de
l'endpoint EUR-Lex (reproduit, pas d'erreur, pas de timeout honoré).
On construit donc l'enveloppe SOAP 1.2 à la main et on POST via httpx.
"""

import os
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

import httpx
from lxml import etree

SERVICE_URL = "https://eur-lex.europa.eu/EURLexWebService"

_ENVELOPE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{password}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <sear:searchRequest xmlns:sear="http://eur-lex.europa.eu/search">
      <sear:expertQuery>{query}</sear:expertQuery>
      <sear:page>{page}</sear:page>
      <sear:pageSize>{page_size}</sear:pageSize>
      <sear:searchLanguage>{language}</sear:searchLanguage>
    </sear:searchRequest>
  </soap:Body>
</soap:Envelope>"""

_NS = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "s": "http://eur-lex.europa.eu/search",
}


class EurLexSoapAPI:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.username = username or os.environ.get("EURLEX_USERNAME")
        self.password = password or os.environ.get("EURLEX_PASSWORD")
        if not self.username or not self.password:
            raise RuntimeError(
                "EURLEX_USERNAME et EURLEX_PASSWORD doivent être définis "
                "(voir .env.example — inscription EU Login requise)."
            )
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def search(
        self,
        expert_query: str,
        page: int = 1,
        page_size: int = 10,
        search_language: str = "fr",
    ) -> Dict[str, Any]:
        """Exécute une requête en langage expert EUR-Lex.

        Référence : https://eur-lex.europa.eu/content/help/eurlex-content/expert-search.html
        Exemples : 'DN = 32014R0651' ou 'TI ~ "aide d\\'état"'

        Depuis le 1ᵉʳ janvier 2026 : max 10 000 résultats par recherche.
        """
        body = _ENVELOPE_TEMPLATE.format(
            username=xml_escape(self.username),
            password=xml_escape(self.password),
            query=xml_escape(expert_query),
            page=int(page),
            page_size=int(page_size),
            language=xml_escape(search_language),
        )
        r = self._client.post(
            SERVICE_URL,
            content=body.encode("utf-8"),
            headers={
                "Content-Type": 'application/soap+xml; charset=utf-8; action=""',
                "Accept": "application/soap+xml, text/xml, application/xml",
            },
        )
        # NB: on ne fait PAS raise_for_status() avant _parse_response() :
        # EUR-Lex renvoie les erreurs métier (syntaxe de requête invalide, etc.)
        # dans un SOAP Fault *à l'intérieur* d'une réponse HTTP 500. On doit
        # parser le body d'abord pour extraire le message d'erreur réel.
        return self._parse_response(r.text, http_status=r.status_code)

    @staticmethod
    def _parse_response(xml_text: str, http_status: int = 200) -> Dict[str, Any]:
        try:
            root = etree.fromstring(xml_text.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise RuntimeError(
                f"Réponse non-XML de EUR-Lex (HTTP {http_status}). "
                f"Extrait : {xml_text[:500]!r}"
            ) from e

        fault = root.find(".//soap:Fault", _NS)
        if fault is not None:
            reason = (
                fault.findtext(".//soap:Reason/soap:Text", namespaces=_NS)
                or fault.findtext(".//soap:Text", namespaces=_NS)
                or "(pas de message)"
            )
            # Code + subcode : ex. "Sender / WS_QUERY_SYNTAX_ERROR"
            code = fault.findtext(".//soap:Code/soap:Value", namespaces=_NS) or ""
            subcode = fault.findtext(".//soap:Subcode/soap:Value", namespaces=_NS) or ""
            code_str = " / ".join(c.split(":")[-1] for c in (code, subcode) if c)

            hint = ""
            if "SYNTAX_ERROR" in subcode.upper():
                hint = (
                    " — Vérifie la syntaxe expert EUR-Lex : champs en MAJUSCULES "
                    "(DN, TI, TE, FM, AU, DD), opérateurs `=` (exact) / `~` (contient) / "
                    "`<`, `>`, `<=`, `>=`, combinaisons `AND` / `OR` / `NOT`. "
                    "N'utilise PAS de syntaxe SQL-like (CONTAINS, LIKE, WHERE)."
                )
            raise RuntimeError(f"SOAP Fault [{code_str}]: {reason}{hint}")

        if http_status >= 400:
            raise RuntimeError(
                f"EUR-Lex HTTP {http_status} sans SOAP Fault exploitable. "
                f"Extrait : {xml_text[:500]!r}"
            )

        results_el = root.find(".//s:searchResults", _NS)
        if results_el is None:
            raise RuntimeError(f"Réponse SOAP inattendue : {xml_text[:500]}")

        return {
            "num_hits": int(results_el.findtext("s:numhits", "0", namespaces=_NS)),
            "total_hits": int(results_el.findtext("s:totalhits", "0", namespaces=_NS)),
            "page": int(results_el.findtext("s:page", "1", namespaces=_NS)),
            "language": results_el.findtext("s:language", "", namespaces=_NS),
            "results": [
                EurLexSoapAPI._parse_result(r) for r in results_el.findall("s:result", _NS)
            ],
        }

    @staticmethod
    def _parse_result(result_el) -> Dict[str, Any]:
        links: Dict[str, str] = {}
        for link in result_el.findall("s:document_link", _NS):
            link_type = link.get("type") or "unknown"
            if link.text:
                links[link_type] = link.text
        return {
            "reference": result_el.findtext("s:reference", namespaces=_NS),
            "rank": int(result_el.findtext("s:rank", "0", namespaces=_NS)),
            "document_links": links,
            "title": result_el.findtext(".//s:EXPRESSION_TITLE/s:VALUE", namespaces=_NS),
        }
