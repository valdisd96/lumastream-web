# Agent entry point

## Read first

- Read `README.md` for architecture, local commands, privacy semantics and the delivery workflow; `CHANGELOG.md` for delivered changes; and `deploy/VERIFICATION.md` for dated deployment evidence and its limits.
- Check the current worktree, GitHub issues, open PRs and CI before continuing. Historical verification is not proof of current cluster health.
- Communicate with the owner in their language. Keep repository documentation, code comments and commit messages in English; maintain both English and Russian website content.

## Required delivery sequence

**Task branch → local checks → PR → successful current CI → squash merge → deployment.**

- Use short-lived `feat/`, `fix/`, `docs/` or `chore/` branches from current `main`; no `develop`. Use separate worktrees for independent parallel tasks. Never copy credentials or `.local/` between worktrees.
- Never commit or push directly to `main`, force-push shared history, bypass CI or use `gh pr merge --admin`. Preserve unrelated changes and stage only task-owned files. Review the full staged diff and check for secrets before committing; never print discovered secret values.
- An approved implementation task permits task-branch commits, push and PR creation. Merge of code, commands, CI or workflow/security policy needs the owner's approval; an explicit request for the full delivery sequence can provide that approval for the agreed scope. A request only to commit does not authorize merge or deployment. Cosmetic prose-only changes may be merged autonomously after CI; policy changes are not cosmetic.
- PRs use `.github/pull_request_template.md`: report actual checks, unverified behavior, risk, approval and deployment/rollback scope. Do not describe a pending or skipped check as passing.
- Before merge, confirm the PR is not draft, has no conflicts, and its current head/base is the revision covered by successful `verify` CI. A changed head or base invalidates the earlier gate. Use squash merge with `--match-head-commit` and the verified head SHA, without bypass flags. Confirm MERGED and inspect the resulting `main` workflow.
- This is an agent workflow, not a claim of GitHub-enforced protection. Inspect current branch protection before relying on it. A head guard alone is not an atomic base/CI guard on an unprotected branch.

## Verification

- Server changes: run `python3 -m unittest discover -s tests -v`. Add regressions for meaningful uncovered failure paths, not source-text or wiring assertions.
- Website changes: launch the real server and inspect the affected EN/RU pages in a browser at desktop and mobile widths. Check navigation, downloads and internal links; verify relevant keyboard/focus behavior. Preserve screenshot attribution and distinguish screenshots from new device verification.
- Deployment/monitoring changes: validate affected resources server-side using authorized cluster access; verify the actual route, target, rule or dashboard after rollout. A healthy Pod does not prove the website or telemetry works.
- Documentation-only changes: check affected links and procedure consistency; no local server test or cluster redeploy is needed solely for prose. Existing PR CI still must pass.
- Update relevant documentation/changelog with observed results and limits. Keep raw captures, downloaded verification artifacts and temporary state in ignored `.local/`; remove throwaway helpers and close only your own sessions/tunnels.

## Deployment gate

- Merge is not deployment permission. Obtain the target, allowed resources, credential use, health checks and rollback scope once; perform routine operations autonomously within that scope. New risks or broader scope require approval.
- Deploy only after the relevant changes are merged and required `main` CI has succeeded. Code/content images must come from successful `main` publication and be pinned by immutable digest in a merged manifest. Follow the separate promotion-PR procedure in README; never apply an uncommitted image-pin edit or a task-branch image.
- Apply from a clean checkout/worktree of the exact merged deployment revision. Record that Git SHA, source/build SHA, image digest, CI run and runtime verification. Documentation-only changes do not trigger a cluster rollout; report it as not needed, not as deployed.
- Own only namespace `lumastream-web` and the application's named HTTPRoute/monitoring resources documented in README. `../k8s-contabo` owns shared platform configuration; the Android app and signed APKs belong to `../lumastream`. Do not duplicate their configuration or rebuild/re-sign APKs for website work.
- Preserve the analytics PVC. One SQLite writer and `Recreate` are invariants; do not add replicas without redesigning persistence. Git revert does not roll back the cluster or restore data. Never delete shared Gateway/certificates or application data as routine rollback.
- Keep Grafana and metrics private. No visitor IDs, cookies, fingerprinting or IP storage in website analytics; page views, redirects, GitHub downloads and installations are distinct concepts. Preserve bounded metric labels.
- Never commit or print kubeconfig, tokens, private keys, Secrets, session cookies or environment dumps. Use authorized existing credentials via secret-safe executors. For Bitwarden, read `/Users/uvauchok/.local/lib/bitwarden-auto/README.md` before using `/Users/uvauchok/.local/bin/bw-auto`; access does not broaden the approved scope.

## Completion report

State the branch/commit/PR, CI result, merge status and deployment status separately. Include the deployed revision/digest and observed checks when deployment occurred; otherwise state why it was not needed or which approval is pending. Do not claim done merely because code was committed, an image was published or Kubernetes accepted a manifest.
