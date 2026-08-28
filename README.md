# Monitor internacional RTX 5090

Rastreador automático de ofertas RTX 5090 en mercados internacionales.

- Consulta canales públicos de Telegram y páginas directas de tiendas.
- Se ejecuta en GitHub Actions cada cinco minutos, aunque el PC esté apagado.
- Publica una lista web valorada y ordenada de mejor a peor.
- Admite tarjetas, reacondicionadas, usadas, portátiles y equipos completos hasta 10.000 €.
- Etiqueta claramente el tipo y el estado para que las ofertas no comparables no parezcan equivalentes.

La pestaña **Actions** permite lanzar una comprobación manual. Los umbrales y fuentes se editan en `config.json`.

Cuando aparece una oferta nueva, el bot crea una incidencia asignada al propietario del repositorio para activar la notificación de GitHub y evitar depender de que la página esté abierta.
