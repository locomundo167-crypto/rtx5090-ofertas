# Monitor internacional RTX 5090

Rastreador automático de ofertas RTX 5090 en mercados internacionales.

- Consulta canales públicos de Telegram y páginas directas de tiendas.
- Se ejecuta en GitHub Actions cuatro veces al día, cada seis horas, aunque el PC esté apagado.
- Revisa en paralelo 78 fuentes entre tiendas, comparadores, marketplaces, foros, agregadores, Reddit y Telegram.
- Limita la presencia de una misma fuente en la página para que una sola tienda no monopolice los resultados.
- Prioriza el precio estructurado del producto, ignora descuentos y cuotas, aplica la moneda local y vuelve a comprobar el precio en la página de la oferta.
- Publica una lista web valorada y ordenada de mejor a peor.
- Admite tarjetas, reacondicionadas, usadas, portátiles y equipos completos hasta 10.000 €.
- Etiqueta claramente el tipo y el estado para que las ofertas no comparables no parezcan equivalentes.

La pestaña **Actions** permite lanzar una comprobación manual. Los umbrales y fuentes se editan en `config.json`.

Cuando aparece una oferta nueva, el bot crea una incidencia asignada al propietario del repositorio para activar la notificación de GitHub y evitar depender de que la página esté abierta.
