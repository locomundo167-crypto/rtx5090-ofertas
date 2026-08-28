# Monitor internacional RTX 5090

Rastreador automático de ofertas RTX 5090 en mercados internacionales.

- Consulta canales públicos de Telegram y páginas directas de tiendas.
- Se ejecuta en GitHub Actions dos veces al día, por la mañana y por la noche, aunque el PC esté apagado.
- Revisa en paralelo más de cuarenta fuentes entre tiendas, comparadores, marketplaces, foros, agregadores y Telegram.
- Publica una lista web valorada y ordenada de mejor a peor.
- Admite tarjetas, reacondicionadas, usadas, portátiles y equipos completos hasta 10.000 €.
- Etiqueta claramente el tipo y el estado para que las ofertas no comparables no parezcan equivalentes.

La pestaña **Actions** permite lanzar una comprobación manual. Los umbrales y fuentes se editan en `config.json`.

Cuando aparece una oferta nueva, el bot crea una incidencia asignada al propietario del repositorio para activar la notificación de GitHub y evitar depender de que la página esté abierta.
