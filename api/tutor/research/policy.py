"""Which web pages may enter a student's knowledge base, and under which licence label."""

from __future__ import annotations

import re
from urllib.parse import urlparse

KNOWN_LICENCES = {
    "wikipedia.org": "CC BY-SA 4.0", "wikibooks.org": "CC BY-SA 4.0", "wikiversity.org": "CC BY-SA 4.0",
    "openstax.org": "CC BY 4.0", "libretexts.org": "CC BY-NC-SA (varies by page)", "ocw.mit.edu": "CC BY-NC-SA 4.0",
    "khanacademy.org": "CC BY-NC-SA (most content)",
}
_CC = re.compile(r"creative\s*commons|\bCC[\s-]?(BY|0)(?:[\s-](SA|NC|ND))*(?:[\s-](SA|ND))?(?:\s*\d\.\d)?", re.I)


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def allowed(url: str, settings) -> tuple[bool, str]:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False, "scheme"
    host = domain_of(url)
    if not host or re.match(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host):
        return False, "private_host"
    if _matches(host, settings.blocked_domains):
        return False, "blocked_domain"
    if settings.allow_any_domain or _matches(host, settings.allowed_domains):
        return True, "ok"
    return False, "not_allowlisted"


def licence_for(url: str, html: str | None = None, meta: dict[str, str] | None = None) -> str:
    host = domain_of(url)
    for d, lic in KNOWN_LICENCES.items():
        if host == d or host.endswith("." + d):
            return lic
    for k in ("license", "dc.rights", "dcterms.license", "rights"):
        if meta and meta.get(k):
            return meta[k][:80]
    if html:
        m = _CC.search(html[-20000:]) or _CC.search(html[:20000])
        if m:
            return m.group(0).strip()[:40]
    return "unknown (quoted with attribution)"
