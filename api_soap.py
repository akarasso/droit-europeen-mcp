"""Client SOAP EUR-Lex — recherche experte plein-texte (nécessite EU Login)."""

import os
from typing import Any, Optional

from zeep import Client
from zeep.wsse.username import UsernameToken

WSDL_URL = "https://eur-lex.europa.eu/EURLexWebService?WSDL"


class EurLexSoapAPI:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.username = username or os.environ.get("EURLEX_USERNAME")
        self.password = password or os.environ.get("EURLEX_PASSWORD")
        if not self.username or not self.password:
            raise RuntimeError(
                "EURLEX_USERNAME et EURLEX_PASSWORD doivent être définis "
                "(voir .env.example — inscription EU Login requise)."
            )
        self._client = Client(
            WSDL_URL,
            wsse=UsernameToken(self.username, self.password),
        )

    def search(
        self,
        expert_query: str,
        page: int = 1,
        page_size: int = 10,
        search_language: str = "fr",
    ) -> Any:
        """Exécute une requête en langage expert EUR-Lex.

        Référence : https://eur-lex.europa.eu/content/help/eurlex-content/expert-search.html
        Exemple : 'DN = 32014R0651' ou 'TI ~ \"aide d'état\"'
        """
        return self._client.service.doQuery(
            expertQuery=expert_query,
            page=page,
            pageSize=page_size,
            searchLanguage=search_language,
        )
