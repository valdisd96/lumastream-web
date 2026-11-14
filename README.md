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

### Agent delivery workflow

[AGENTS.md](AGENTS.md) is the agent entry point. Use short-lived `feat/`, `fix/`,
`docs/` or `chore/` branches from current `main`, with PRs and squash merges; there
is no `develop` branch.

**Task branch → local checks → PR → successful current CI → merge → deployment.**

1. Inspect current GitHub/worktree state; preserve unrelated changes. Implement on
   a task branch, update relevant documentation, and run the checks that exercise
   the change. Server changes use the unittest command above; UI changes require
   real desktop/mobile EN/RU browser checks. Prose-only changes need link/procedure
   checks, not a cluster rollout.
2. Review the full staged diff for scope and secrets, then commit/push the task
   branch and open a PR using the repository template. Report actual results and
   known limits. Never push directly to `main` or bypass failed checks.
3. Wait for successful `verify` CI for the current PR head/base. Missing, skipped,
   cancelled or obsolete checks do not pass the gate. Confirm no draft/conflicts;
   changed head/base requires renewed CI. The PR `publish` job is intentionally
   skipped: image publication occurs only on `main`.
4. Obtain owner approval for merging code, commands, CI or workflow/security policy.
   An explicit full-delivery request can authorize this within its scope; a request
   only to commit cannot. Cosmetic prose may merge autonomously after CI, but policy
   changes are not cosmetic. Use `gh pr merge --squash --match-head-commit` with the
   verified head SHA, never `--admin`. Confirm MERGED and the resulting `main` CI.
5. Deploy only within an approved operational scope, from a clean checkout of the
   exact merged deployment revision, after the relevant `main` checks/publication
   succeed. Record source/build SHA, deployment SHA, digest, CI run, runtime checks
   and rollback. Commit verification evidence through a subsequent PR rather than
   directly to `main`. For prose-only changes, report deployment as **not needed**.

These are agent rules, not a claim that GitHub branch protection enforces them.
At adoption, `main` was unprotected; this documentation change does not configure
repository protection or automatic deployment. Recheck current settings before
relying on a technical gate. On an unprotected branch, a head-SHA guard alone does
not atomically guard concurrent base/CI changes.

Commit/push, merge, image publication and cluster rollout are distinct operations.
GitHub Actions currently verifies every PR and verifies/publishes each `main`
push, including documentation-only pushes; it does **not** deploy Kubernetes.
Report each operation's actual status, including any pending owner approval.

## Release source

The site deliberately points at the exact published **v0.9.1 preview**, not GitHub `/releases/latest` (which excludes previews). APKs remain hosted by GitHub; the website never rebuilds or re-signs them. For a new release, update the exact tag and asset allowlist in `server.py` and both translations in one source PR, then promote the published website image through the separate deployment PR described below. Keep SHA256SUMS and release links paired with the APK.

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

GitHub Actions verifies tests and publishes `ghcr.io/valdisd96/lumastream-web:<commit>` on `main`. All third-party actions and the Python base image are digest/SHA-pinned. Public image pull access must be verified before rollout. Deployment uses the **published digest**, never `latest`, and requires the workflow and operational approval above.

Because publication occurs after merge, an application release uses two PRs:

1. Merge the source/content change after its checks and approval, then wait for
   successful `verify` and `publish` jobs on that exact `main` source revision.
2. Resolve its published image digest. In a new promotion task branch, pin that
   digest in `deploy/application.yaml` and record its source SHA/publication run in
   the PR. Run relevant manifest checks, obtain approval, and merge after current
   PR CI succeeds.
3. Wait for the promotion revision's `main` workflow, then apply the committed
   manifests from a clean checkout of that merged revision. The promotion push
   also publishes an image, but the intended application image remains the
   source revision's explicitly selected digest; do not chase the new tag.

Manifest/dashboard-only changes use the same PR/CI/merge gate and may retain the
existing verified image digest. Never deploy a local pin before its promotion PR
is merged. Neither a successful build nor a merge alone proves runtime health.

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
