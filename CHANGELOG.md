# Changelog

## Initial website

- Add an English/Russian cinematic landing page, exact signed-preview downloads, installation guides, FAQ and privacy/attribution information.
- Keep the Android app and release assets in their original repository; this repository owns only the website and its deployment.
- Add durable aggregate page-view/download-redirect counters without visitor identifiers, separate GitHub asset statistics, bounded HTTP metrics and private Prometheus scraping.
- Add a dedicated namespace, persistent analytics storage, restricted workload/network access and an additive route through the existing HTTPS Gateway.
- Provision a separate Grafana dashboard with traffic, download, freshness, availability, error, latency and resource panels, plus scoped monitoring rules.
