import re
from urllib.parse import urlsplit

import requests

from .classification import normalize


class WebResearchProvider:
    name = "disabled"

    def research(self, facts):
        return {"provider": self.name, "query": self.query(facts), "sources": [], "error": "Web research is not configured"}

    @staticmethod
    def query(facts):
        name = facts.get("name") or facts.get("card_name") or facts.get("code") or ""
        return ('"' + name.replace('"', " ") + '" ' + (facts.get("manufacturer") or ""))[:500]


class BraveResearchProvider(WebResearchProvider):
    name = "brave"

    def __init__(self, api_key, trusted_domains):
        self.api_key = api_key
        self.trusted_domains = {d.strip().lower() for d in trusted_domains if d.strip()}

    def research(self, facts):
        query = self.query(facts)
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            params={"q": query, "count": 5, "text_decorations": False},
            timeout=(3, 8), allow_redirects=False,
        )
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected research provider response")
        sources = []
        name = normalize(facts.get("name") or facts.get("card_name") or "")
        for row in response.json().get("web", {}).get("results", []):
            url = row.get("url", "")
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            if parsed.scheme != "https" or not any(host == domain or host.endswith("." + domain) for domain in self.trusted_domains):
                continue
            title = re.sub("<[^>]*>", "", row.get("title", ""))[:500]
            evidence = re.sub("<[^>]*>", "", row.get("description", ""))[:3000]
            text = normalize(title + " " + evidence)
            tokens = name.split()
            if len(tokens) < 2 or not all(token in text.split() for token in tokens):
                continue
            sources.append({"url": url, "title": title, "evidence": evidence})
        return {"provider": self.name, "query": query, "sources": sources, "error": ""}
