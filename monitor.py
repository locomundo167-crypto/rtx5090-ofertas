from __future__ import annotations
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
STATE = ROOT / "state.json"
LATEST = ROOT / "latest.md"
ALERTS = ROOT / "new_offers.json"
DOCS = ROOT / "docs" / "index.html"

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

def clean(markup):
    markup = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", markup, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).casefold()


class ProductLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join(self.parts)))
            self.href = None


def discover(source, markup, timeout):
    parser = ProductLinks()
    parser.feed(markup)
    candidates = []
    for href, label in parser.links:
        url = urljoin(source["url"], href)
        title = clean(label)
        if urlsplit(url).hostname != urlsplit(source["url"]).hostname:
            continue
        if not re.match(r"^/videojuegos/A[0-9]+-", urlsplit(url).path):
            continue
        if not all(term in title for term in ("consola", "switch 2", "zelda", "40")):
            continue
        if any(term in title for term in ("mando", "funda", "protector", "oled")):
            continue
        if url not in candidates:
            candidates.append(url)
    if not candidates:
        return {"id": source["id"], "name": source["name"], "url": source["url"], "verified": False, "available": False, "detail": "Buscando ficha de la consola; sin coincidencia confirmada"}
    results = []
    for url in candidates[:3]:
        product = dict(source, url=url, mode="product", structured_only=True)
        results.append(check(product, timeout))
    return next((row for row in results if row["available"]), results[0])


def structured_stock(markup):
    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
    for raw in re.findall(r'<script[^>]+type=["\x27]application/ld\+json["\x27][^>]*>(.*?)</script>', markup, re.I | re.S):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        for item in walk(data):
            kind = item.get("@type", [])
            kind = [kind] if isinstance(kind, str) else kind
            title = clean(str(item.get("name", "")))
            if "Product" not in kind or not all(x in title for x in ("consola", "switch 2", "zelda", "40")):
                continue
            for offer in walk(item.get("offers", [])):
                status = str(offer.get("availability", "")).rsplit("/", 1)[-1]
                if status in ("InStock", "PreOrder", "LimitedAvailability"):
                    return True
                if status in ("OutOfStock", "SoldOut", "Discontinued"):
                    return False
    return None


def check(source, timeout):
    row = {"id": source["id"], "name": source["name"], "url": source["url"], "verified": False, "available": False}
    try:
        request = Request(source["url"], headers={"User-Agent": "Mozilla/5.0 (ZeldaStockMonitor/1.0)", "Accept-Language": "es-ES,es;q=0.9"})
        with urlopen(request, timeout=timeout) as response:
            markup = response.read().decode("utf-8", errors="replace")
            text = clean(markup)
    except (OSError, URLError, TimeoutError) as error:
        row["detail"] = f"No verificable: {error}"
        return row
    if source.get("mode") == "discovery":
        return discover(source, markup, timeout)
    if source.get("structured_only"):
        available = structured_stock(markup)
        row.update(verified=available is not None, available=available is True, detail="Reserva o compra detectada" if available else ("Aún no disponible" if available is False else "Ficha localizada; disponibilidad sin confirmar"))
        return row
    if not all(x.casefold() in text for x in source["required_terms"]):
        row["detail"] = "La página no confirmó el producto exacto"
    elif any(x.casefold() in text for x in source["unavailable_terms"]):
        row.update(verified=True, detail="Aún no disponible")
    elif any(x.casefold() in text for x in source["available_terms"]):
        row.update(verified=True, available=True, detail="Reserva o compra detectada")
    else:
        row.update(verified=True, detail="Estado no concluyente; no se avisará")
    return row

def main():
    config = load(CONFIG, {})
    old = load(STATE, {"sources": {}}).get("sources", {})
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    rows = [check(s, config.get("timeout_seconds", 25)) for s in config.get("sources", [])]
    alerts, sources = [], dict(old)
    for row in rows:
        previous = old.get(row["id"], {})
        if row["verified"]:
            if row["available"] and not previous.get("available", False):
                alerts.append(row)
            sources[row["id"]] = {"available": row["available"], "checked_at": now}
    STATE.write_text(json.dumps({"sources": sources, "last_run": now}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ALERTS.write_text(json.dumps(alerts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = ["# Seguimiento: Nintendo Switch 2 Zelda 40.º aniversario", "", f"Última comprobación: **{now}**.", "", "| Tienda | Estado | Enlace |", "|---|---|---|"]
    for row in rows:
        status = "✅ Disponible" if row["available"] else ("⚪ No verificado" if not row["verified"] else "⏳ No disponible")
        report.append(f"| {row['name']} | {status}: {row['detail']} | [Abrir]({row['url']}) |")
    LATEST.write_text("\n".join(report) + "\n", encoding="utf-8")
    DOCS.parent.mkdir(exist_ok=True)
    DOCS.write_text("<!doctype html><meta charset=utf-8><title>Reservas Zelda Switch 2</title><h1>Switch 2 Zelda 40.º aniversario</h1><p>El último estado se publica en latest.md.</p>", encoding="utf-8")
    print(f"Comprobadas {len(rows)} tiendas; alertas nuevas: {len(alerts)}")

if __name__ == "__main__":
    main()
