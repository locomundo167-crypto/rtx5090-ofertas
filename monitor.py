from __future__ import annotations
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
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

def check(source, timeout):
    row = {"id": source["id"], "name": source["name"], "url": source["url"], "verified": False, "available": False}
    try:
        request = Request(source["url"], headers={"User-Agent": "Mozilla/5.0 (ZeldaStockMonitor/1.0)", "Accept-Language": "es-ES,es;q=0.9"})
        with urlopen(request, timeout=timeout) as response:
            text = clean(response.read().decode("utf-8", errors="replace"))
    except (OSError, URLError, TimeoutError) as error:
        row["detail"] = f"No verificable: {error}"
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
