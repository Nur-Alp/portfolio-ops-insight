# IdP registration request — Portfolio Operations Insight dashboard

Hand this to whoever administers the organization's identity provider
(Azure AD / Okta / similar). It lists exactly what needs to be registered
and configured, and exactly what values need to come back. Nothing in
this app's code is missing or unbuilt — both the backend token validation
and the frontend login flow are already implemented and tested against
synthetic tokens; this document is the only remaining gap before pointing
them at the real IdP.

## 1. Register the application

Register **two** clients (or one client with two redirect URIs / grant
types, depending on the IdP - an API/resource registration plus a
browser/SPA registration is the common pattern for Azure AD and Okta
alike):

- **API (resource) registration** — the backend validates bearer tokens
  issued for this. Needs its own client ID, which becomes the `audience`
  below.
- **Browser (SPA/public) registration** — the frontend uses this for the
  interactive login redirect (Authorization Code + PKCE, no client
  secret in the browser). Needs a redirect URI:
  `https://<the real server's hostname>/auth/callback`
  (exact hostname is whatever the real server ends up being reachable at
  - not yet finalized as of this request).

## 2. Values needed back

| What | Used by | Notes |
|---|---|---|
| Issuer URL | Backend `OSIP_OIDC_ISSUER` | e.g. `https://login.microsoftonline.com/<tenant-id>/v2.0` for Azure AD, or the Okta org's issuer URL. |
| API audience / client ID | Backend `OSIP_OIDC_AUDIENCE` | The **API** registration's identifier, not the browser one. |
| JWKS URL | Backend `OSIP_OIDC_JWKS_URL` | Usually discoverable from `<issuer>/.well-known/openid-configuration` as `jwks_uri`, but ask for the exact URL directly rather than deriving it. |
| Browser authority | Frontend `VITE_OIDC_AUTHORITY` | Usually the same as the issuer URL; confirm they match. |
| Browser client ID | Frontend `VITE_OIDC_CLIENT_ID` | The **browser/SPA** registration's identifier, not the API one. |
| Redirect URI | Frontend `VITE_OIDC_REDIRECT_URI` | Must be registered on the IdP side exactly (scheme, host, path, trailing slash all matter) before login will work. |
| Signing algorithm | Backend `OSIP_OIDC_ALGORITHMS` | Must be an asymmetric algorithm (RS256, ES256, etc.) - **the app will refuse to start if a symmetric algorithm like HS256 is configured for OIDC**, so confirm which asymmetric algorithm the IdP signs with (RS256 is the near-universal default for Azure AD/Okta). |

## 3. Claims this app needs in the token

The IdP needs to be configured to include three **custom** claims in
issued tokens - these are specific to this app, not something a generic
corporate SSO setup includes out of the box. Someone will need to decide
how they map to the org's existing group/role structure (Azure AD App
Roles or group claims, Okta custom claims/groups, etc.):

- **`roles`** (or a different claim name - a real one is chosen with
  `OSIP_OIDC_ROLES_CLAIM`): a list of role identifiers, each of which
  will map to exactly one of this app's four internal roles:
  `uploader`, `reviewer`, `publisher`, `reader`. The IdP's own role/group
  names don't need to match these - a mapping table (external name ->
  internal role) is provided separately as `OSIP_OIDC_ROLE_MAPPING`, so
  e.g. an Azure AD App Role called `OSIP.Accounting.Upload` can map to
  `uploader`. **What's needed back:** the exact list of role/group values
  the IdP will actually send, so the mapping table can be written.

- **`domains`** (claim name via `OSIP_OIDC_DOMAINS_CLAIM`): a list of
  which business domain(s) a person can access. Valid values are exactly:
  `risk`, `accounting`, `back_office`, `client_ops`, `corpfin` — or the
  single literal value `*` for all-domain access (used for a small number
  of oversight/observer accounts, analogous to today's demo `supervisor`
  persona).

- **`portfolios`** (claim name via `OSIP_OIDC_PORTFOLIOS_CLAIM`): a list
  of which portfolio(s) a person can access. Valid values are exactly:
  `SOBSTV`, `TABYS` — or the literal value `*` for all-portfolio access.

**A token with no `domains` claim at all is treated as legacy/all-domain
access** (a deliberate compatibility default, not a bug) - so once real
tokens are flowing, every one of them should carry an explicit `domains`
claim, even if it's just `["*"]` for an observer account. An empty list
`[]` correctly means "no domain access," which is different from the
claim being absent entirely.

## 4. What "done" looks like

Once the values above exist, wiring them in is a configuration change
only (no code): set the backend env vars (`OSIP_IDENTITY_PROVIDER=oidc`,
the `OSIP_OIDC_*` values above, `OSIP_OIDC_ROLE_MAPPING` as a JSON object)
and the frontend build args (`VITE_AUTH_MODE=oidc`, the `VITE_OIDC_*`
values above) and deploy via `compose.production.yaml` — see
`docs/deployment-runbook.md`. `docs/production-readiness-checklist.md`
still gates any release regardless of how identity is wired.

## 5. Who to loop in

- Whoever administers the org's Azure AD / Okta tenant, for the
  registration and custom claims (section 1 and 3).
- Whoever decides which people/groups get which of the five domains and
  two portfolios above (section 3's `roles`/`domains`/`portfolios`
  mapping) - this is a business access-control decision, not an IT one,
  and should be made explicitly rather than defaulted.
