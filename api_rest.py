"""Client REST CELLAR — récupération directe de documents et métadonnées par CELEX."""

from typing import Literal, Optional
import httpx

CELLAR_BASE = "http://publications.europa.eu/resource/celex"

NoticeType = Literal["object", "branch", "tree", "identifiers"]
ContentFormat = Literal["html", "pdf", "xml"]

# NB : CELLAR ne sert pas toujours tous les formats pour un document donné.
# 'html' est aliasé sur application/xhtml+xml qui est le format de contenu
# structuré le plus largement disponible ; 'xml' tente le FORMEX officiel.
_ACCEPT_CONTENT = {
    "html": "application/xhtml+xml",
    "xml": "application/xml;notice=branch",
    "pdf": "application/pdf",
}


class CellarRestAPI:
    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def get_notice(self, celex: str, notice: NoticeType = "object", language: str = "fra") -> str:
        """Récupère la notice de métadonnées XML pour un identifiant CELEX."""
        url = f"{CELLAR_BASE}/{celex}"
        headers = {
            "Accept": f"application/xml;notice={notice}",
            "Accept-Language": language,
        }
        r = self._client.get(url, headers=headers)
        r.raise_for_status()
        return r.text

    def get_content(
        self,
        celex: str,
        format: ContentFormat = "html",
        language: str = "fra",
    ) -> bytes:
        """Récupère le contenu du document (HTML, PDF, XML) pour un CELEX donné."""
        url = f"{CELLAR_BASE}/{celex}"
        headers = {
            "Accept": _ACCEPT_CONTENT[format],
            "Accept-Language": language,
        }
        r = self._client.get(url, headers=headers)
        r.raise_for_status()
        return r.content

    def exists(self, celex: str) -> bool:
        url = f"{CELLAR_BASE}/{celex}"
        r = self._client.head(url)
        return r.status_code < 400
