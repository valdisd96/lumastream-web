# LumaStream web

Bilingual, self-hosted website for [LumaStream](https://github.com/valdisd96/lumastream): real app screenshots, signed preview download, installation guide, FAQ and privacy notes.

- Website: https://uvauchok-lab.duckdns.org/lumastream/
- Russian: https://uvauchok-lab.duckdns.org/lumastream/ru/
- Private dashboard: http://127.0.0.1:3000/d/lumastream-web (existing Contabo Grafana tunnel and login required).

## Development

Python 3.9+; no third-party runtime or frontend dependencies.

```sh
mkdir -p .local/data
DATA_DIR="$PWD/.local/data" STATIC_DIR="$PWD/public" python3 server.py
# http://127.0.0.1:8080/lumastream/
python3 -m unittest discover -s tests -v
```

`public/` contains ordinary HTML/CSS and reviewed screenshots. `server.py` serves the site on 8080 and Prometheus metrics on a **separate** 9090 listener. Do not publish 9090 to the internet. There is no tracking script, third-party font request or frontend build chain.

## Release source

The site deliberately points at the exact published **v0.9.1 preview**, not GitHub `/releases/latest` (which excludes previews). APKs remain hosted by GitHub; the website never rebuilds or re-signs them. For a new release, update the exact tag and asset allowlist in `server.py`, both translations, and deployment image in one reviewed change. Keep SHA256SUMS and release links paired with the APK.

## Metrics and privacy

- `lumastream_page_views_total{page,language}`: successful HTML GET requests; known bots and prefetch requests are excluded. Not unique visitors; undetected bots/reloads count. HEAD, assets, unknown routes and health checks are not page views.
- `lumastream_download_redirects_total{asset}`: redirects from this site, **not completed downloads or installs**. APK and checksums are separate.
- `lumastream_github_asset_downloads{version,asset}`: GitHub's asset `download_count`, including traffic from all origins. Refreshed every 15 minutes; last successful sample survives a refresh failure. The freshness/success metrics expose this distinction.
- Aggregate counters are stored transactionally in SQLite on the analytics PVC; no IP addresses, user agents, referrers, cookies or visitor IDs are stored by the application. Network infrastructure necessarily processes client addresses; this is not a claim about third-party GitHub infrastructure.
- HTTP request counts and duration histograms are operational process metrics. Labels are bounded; arbitrary URLs do not create time series.
- Existing Prometheus retention is **48 hours**. Range increases are sampled/extrapolated estimates; durable all-time counters are not a historical daily-event database. The Grafana dashboard states these distinctions explicitly.

## Kubernetes deployment

Application ownership stays in this repository, not in the cluster platform repository. `../k8s-contabo` owns the existing Gateway, certificate, cluster access and monitoring installation.

`deploy/application.yaml` creates namespace `lumastream-web`, restricted Pod Security, resource quota, a single non-root read-only-root-filesystem application, a 1 GiB Longhorn PVC, Service, scoped Cilium policy and ReferenceGrant. An HTTPRoute in `gateway-demo` attaches to its existing HTTPS listener and may reference only this Service. **No change to Gateway listeners, firewall, platform versions or existing application routes is required.** The existing HTTP redirect also covers `/lumastream/`.

`deploy/monitoring.yaml` adds a ServiceMonitor, public-HTTPS Probe and alert rules in `monitoring`; `deploy/dashboard.json` provisions a separate dashboard. Grafana and metrics stay private. The probe exercises the public HTTPS route from inside the cluster, not an independent external network.

The one-writer SQLite deployment uses `Recreate`: updates briefly interrupt service. Longhorn replication handles storage replicas, not multi-instance application availability. The existing single edge remains a platform single point of failure. The PVC has Retain semantics; it is not an offsite backup, and losing it loses the cumulative website counters. No existing platform backup/retention policy is silently changed.

### Publish and deploy

GitHub Actions verifies tests and publishes `ghcr.io/valdisd96/lumastream-web:<commit>` on `main`. All third-party actions and the Python base image are digest/SHA-pinned. Public image pull access must be verified before rollout. Replace the deployment image with the **published digest**, never `latest`.

Use the existing kubeconfig without printing it:

```sh
export KUBECONFIG="$HOME/.kube/contabo-lab-admin.json"
# On this Mac kubectl is supplied by Freelens:
export PATH="$HOME/Applications/Freelens.app/Contents/Resources/arm64:$PATH"
kubectl apply --dry-run=server -f deploy/application.yaml
kubectl apply -f deploy/application.yaml
kubectl rollout status -n lumastream-web deployment/lumastream-web --timeout=180s
kubectl apply -f deploy/monitoring.yaml -f deploy/dashboard.json
kubectl get httproute -n gateway-demo lumastream-web
curl --fail https://uvauchok-lab.duckdns.org/lumastream/healthz
```

For a first install, create the namespace before server-side dry-run of namespaced resources. Check ReferenceGrant/route `Accepted` and `ResolvedRefs`, Prometheus target/rules, HTTPS and EN/RU navigation. Inspect desktop/mobile views in a browser; a healthy Pod is not UI verification.

### Rollback

Reapply the previous known-good immutable image and wait for readiness. To withdraw only the public website, delete **only** HTTPRoute `gateway-demo/lumastream-web` after operator approval; do not delete the shared Gateway/certificate, namespace or analytics PVC. Monitoring resources are individually named `lumastream-web` (dashboard ConfigMap `lumastream-web-dashboard`). Removing a route does not remove data. Preserve the PVC across upgrades.

## Content attribution

Screenshots are real app captures from the 0.8.0 verification sessions, not newly verified 0.9.1 device captures. Sintel © Blender Foundation, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); TMDB metadata/artwork is not included video content or endorsement. See the site's credits and the [source screenshot record](https://github.com/valdisd96/lumastream/blob/main/docs/images/README.md).
