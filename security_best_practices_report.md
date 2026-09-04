# Security review for public repository readiness

Review date: 2026-09-02

Scope: the current working tree, all reachable Git history, the FastAPI backend,
the GitHub Pages frontend, the Web Push implementation, dependencies, and the
scheduled GitHub Actions scanner.

## Conclusion

No critical or high-severity unresolved security issue was found. No credential,
private key, environment file, or recognizable provider token was found in the
current tree or reachable Git history. The repository is suitable to make public
after the deployment-only secrets listed in the README are created in Render and
GitHub, and only if those values remain outside Git.

The repository is still private at the time of this review. Changing visibility
was intentionally left as a separate, explicit owner action.

## Resolved findings

### Medium: API-provided text could reach HTML parsing sinks

The dashboard previously assembled trigger and alert history rows with
`innerHTML`. Because parts of those values originate in backend responses, a
compromised or malformed upstream response could have injected markup into the
dashboard.

Resolution: dynamic rows now use `createElement`, `textContent`, and
`replaceChildren` in `static/index.html` around lines 1069 through 1098 and 1155
through 1189. Inline event-handler attributes were also removed.

### Medium: notification and scanner operations needed authentication

Subscription mutation, test delivery, and scheduled scan endpoints could be
abused if exposed without access control.

Resolution: FastAPI bearer-token dependencies protect these routes in `app.py`
around lines 345 through 395 and 671 through 676. Token comparison uses
`secrets.compare_digest`. Real HTTP checks confirmed that missing and incorrect
tokens receive HTTP 401.

### Medium: browser push endpoints create an outbound-request boundary

A user-supplied PushSubscription endpoint is later contacted by the server. If
arbitrary endpoints were accepted, this could become server-side request
forgery.

Resolution: `push_notifications.py` around lines 66 through 93 accepts only HTTPS
endpoints belonging to known browser push providers, rejects credentials and
custom ports, and validates subscription key encoding and size.

### Medium: third-party script and inline-script controls were incomplete

Resolution: the chart library is pinned and protected with Subresource Integrity
in `static/index.html` around lines 14 through 18. A restrictive Content Security
Policy is declared around lines 7 through 10. The policy permits only this site,
the pinned chart host, the Render API, and the minimum inline styling needed by
the existing dashboard.

### Low: default API hardening was incomplete

Resolution: `app.py` around lines 46 through 90 disables API documentation by
default, restricts CORS methods and headers, validates host headers, and adds
content-type, framing, referrer, camera, microphone, and geolocation protections.

### Low: push delivery state needed durable, non-public storage

Resolution: browser subscriptions and sent-event identifiers are stored in
Firestore through a server service account. `firestore.rules` denies all direct
client access. Subscription documents use SHA-256 identifiers instead of raw
endpoint capability URLs as document names.

## Verification performed

- Searched current files and reachable Git history for common credentials,
  provider tokens, private keys, and secret-file extensions. No match was found.
- Ran `pip-audit` against `requirements.txt`. No known vulnerability was found.
- Ran both unittest suites. All 41 tests passed.
- Ran Python bytecode compilation and `pip check`. Both passed.
- Loaded the dashboard in Chromium with Playwright. The page rendered, the new
  alert control was present, the Content Security Policy allowed the intended
  scripts, and the service worker registered at the expected scope.
- Exercised the protected endpoints through a running Uvicorn server. Missing and
  incorrect tokens returned 401; correct test tokens reached the protected
  handler and failed closed because Firebase production credentials were absent.

## Remaining operational considerations

### Low: public market-data endpoints have no application rate limiter

`/api/analysis` and `/api/backtest` remain public and can cause Yahoo Finance
requests or CPU work. Existing caching limits repeated market-data downloads, and
Render provides platform-level controls, but a dedicated API rate limiter would
be appropriate if traffic grows or abuse appears.

### Low: one shared subscription code is intended for a small trusted audience

`SUBSCRIPTION_ACCESS_TOKEN` is suitable for the owner and a few trusted users. It
is not a user-account system. If subscriptions are offered broadly, replace it
with per-user authentication and authorization.

### Informational: external behavior cannot be guaranteed by this repository

Yahoo Finance can rate-limit requests, GitHub scheduled workflows can start
late, Render free instances can take time to wake, and browsers or operating
systems can suppress notifications. These are reliability constraints, not
repository disclosure risks.

### Informational: add an open-source license if reuse is intended

Making a repository public makes its source readable, but it does not grant a
reuse license. Add a LICENSE file only after choosing the rights you want to
grant.
