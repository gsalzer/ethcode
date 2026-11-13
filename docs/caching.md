# Caching

Each provider stores validated raw responses from its outgoing API calls. The
cache avoids repeated network requests while preserving the provider envelope
used to derive normalized artifacts.

The default cache parent is `~/.cache/ethcode`:

```text
~/.cache/ethcode/
├── etherscan/
└── sourcify/
```

Each provider accepts `cache_dir` to override its default subdirectory.

## Entry format

Every JSON entry includes a cache format number. Provider entries add the raw
response and classification or HTTP status required to decode it. Files are
written through atomic replacement.

Cache reads validate the format and provider-specific structure. Malformed
entries raise `CacheError` or `ProviderUnavailableError` and remain available
for inspection.

## Etherscan

Etherscan uses independent source, creation, and runtime entries:

```text
<cache>/source/<chain-id>/<address>.json
<cache>/creation/<chain-id>/<address>.json
<cache>/runtime/<chain-id>/<address>.json
```

A retrieval requests only missing entries for the selected artifact kinds.
Successful calls completed before a later endpoint failure remain cached.

`.request.lock` and `.request-schedule.json` coordinate request spacing across
threads and processes sharing the cache directory.

## Sourcify

Sourcify uses one contract-response entry:

```text
<cache>/contract/<chain-id>/<address>.json
```

That response supplies all artifact kinds. `.request.lock` and `.cooldown.json`
coordinate normal delays, exponential backoff, and `Retry-After` across callers.

## Cacheability

The cache records:

- successful provider responses;
- provider responses classified as authoritative absence.

Transport failures, invalid JSON, rate-limit responses, quota responses,
malformed values, and ambiguous API errors remain retryable and create no entry.

The [Sourcify dataset importer](sourcify_dataset.md) writes successful
API-shaped responses through the provider's validated cache-import interface.

