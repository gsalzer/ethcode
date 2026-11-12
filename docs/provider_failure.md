# `ProviderFailure`: Structured failure context

`ProviderFailure` records provider, category, safe detail, retryability, origin,
optional failed kind, completed kinds, optional HTTP status, and
JSON-compatible details. `as_dict()` returns a JSON-compatible representation.

Categories distinguish credentials, DNS, TLS, timeout, connection, HTTP, rate
limit, quota, invalid JSON, invalid provider response, cache corruption,
request scheduling, and unknown operational failures. Complete URLs, API keys,
and sensitive response bodies are excluded.
