# Changelog

## Initial website

- Add an English/Russian cinematic landing page, exact signed-preview downloads, installation guides, FAQ and privacy/attribution information.
- Keep the Android app and release assets in their original repository; this repository owns only the website and its deployment.
- Add durable aggregate page-view/download-redirect counters without visitor identifiers, separate GitHub asset statistics, bounded HTTP metrics and private Prometheus scraping.
- Add a dedicated namespace, persistent analytics storage, restricted workload/network access and an additive route through the existing HTTPS Gateway.
- Provision a separate Grafana dashboard with traffic, download, freshness, availability, error, latency and resource panels, plus scoped monitoring rules.
- Verify eight server regressions locally and in CI, all internal links, desktop/mobile layouts, public HTTPS navigation, a complete APK download with matching SHA-256, and durable counters across an actual Kubernetes Pod replacement.
- Verify both Prometheus targets, four healthy alert rules and the populated private Grafana dashboard. Preserve the existing 48-hour metrics retention; document single-replica update downtime and lack of an offsite analytics backup in [deployment evidence](deploy/VERIFICATION.md).
