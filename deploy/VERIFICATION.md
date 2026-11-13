# Deployment verification — 2026-11-14

The deployment was requested by the owner with permission for a public sibling repository, the `/lumastream/` path, a dedicated namespace, aggregate-only analytics and integration with existing private monitoring. UTC cluster/CI timestamps begin on November 13; the local session crossed midnight.

## Delivered

- Repository: https://github.com/valdisd96/lumastream-web
- Runtime source revision: `46c1135172888cfe2c6d67d37899e70d567a8caf`.
- CI run [43524892667](https://github.com/valdisd96/lumastream-web/actions/runs/43524892667): eight server regressions passed; container published successfully.
- Image: `ghcr.io/valdisd96/lumastream-web@sha256:abf6ed3c31bd0bf554d517cd8aa41a0398d8ddcd78b74bcfd259950876927691`. Anonymous registry pull authorization succeeded; no registry credential was placed in the namespace.
- Namespace `lumastream-web`; one ready non-root application replica; 1 GiB `analytics` PVC Bound on Longhorn. Existing platform workloads, Gateway listeners, firewall and certificates were not changed.
- HTTPRoute `gateway-demo/lumastream-web`: `Accepted=True`, `ResolvedRefs=True`. Cross-namespace access uses a named-Service ReferenceGrant.

## Exercised

- All 20 distinct internal page/asset/download links checked with HEAD locally. Desktop landing and Russian 390 px mobile landing/download/guide were exercised in Chromium; no horizontal overflow was observed. FAQ disclosure opened correctly.
- Public HTTPS landing rendered in Chromium. Language switch to Russian and navigation to the download page worked on the public site. Existing HTTP redirect returns 308 to HTTPS.
- Public `/lumastream/healthz` returns 200; `/lumastream/metrics` returns 404. Metrics are served only on the separate listener.
- Downloaded the entire published APK through the website redirect and downloaded its SHA256SUMS; `shasum -a 256 -c SHA256SUMS` returned **OK**. This verifies transfer integrity, not renewed Android runtime or signing-certificate verification.
- Replaced the actual Kubernetes application Pod using a scoped rollout restart. Durable page/redirect aggregates read from SQLite before and after were preserved; readiness recovered normally. The acceptance downloads and page views remain included in the aggregate counters.
- Prometheus discovered both the ServiceMonitor and public HTTPS Probe; both targets reported `up`, with no scrape error. The four website alert rules reported evaluation health `ok` and state `inactive`.
- All 18 dashboard expressions were accepted by Prometheus. Page/redirect totals, GitHub sample/freshness, HTTPS health, scrape health, CPU, memory, deployment availability and restart data were returned. Kubelet subsequently reported analytics volume usage (114,688 bytes at that observation). Rates require at least two scrape samples; zero traffic does not imply missing instrumentation.
- The private Grafana dashboard rendered actual counters, healthy HTTPS/scraping indicators and traffic series in an authenticated browser. Provisioning, not a manual UI-only dashboard edit, owns the dashboard.

## Boundaries

This is a low-traffic functional deployment check, not a load test, accessibility certification, disaster-recovery drill, failover test or new Android verification. One application replica plus SQLite uses Recreate and has a brief update outage. Longhorn replication and persistent counters do not constitute an offsite analytics backup. The single edge remains a platform availability limitation.

Monitoring time series retain the existing 48-hour policy. Totals survive application restarts, but historical daily analytics are not stored indefinitely. Page views are requests, not unique people. Redirects are not completed downloads or installs. GitHub counts include all origins and are refreshed every 15 minutes. The public HTTPS probe runs inside the cluster, not from an independent external observer.

Existing unrelated Rental critical alerts were present before deployment; they were neither silenced nor repaired as part of this website task. The website alert rules were not deliberately fired to test notification delivery.
