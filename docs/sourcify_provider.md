# `SourcifyProvider`

Sourcify API V2 supplies all requested kinds from one contract response. The
provider reads `SOURCIFY_EMAIL` and includes contact and project information in
its User-Agent. Its constructor also configures timeout, interval, retries,
backoff, maximum shared cooldown wait, SSL context, or CA file.

Match fields, compiler version, API or dataset origin, and cache status are
retained in provenance. A verified response may still produce an absent
outcome for an unavailable individual artifact.

`response_cached(location)` checks for an existing validated response envelope.
`store_response(location, response, provenance=...)` validates and stores an
API-shaped dataset response without overwriting an existing entry.
