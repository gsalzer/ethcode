# Errors

All package exceptions derive from `ArtifactError`.

```text
ArtifactError
├── InvalidArtifactError (also ValueError)
├── ProviderError
│   └── ProviderUnavailableError
│       └── ProviderLimitError
│           ├── ProviderRateLimitError
│           └── ProviderQuotaError
├── ArtifactConflictError (also ValueError)
└── CacheError
```

## Input and artifact errors

`InvalidArtifactError` reports malformed addresses, chain IDs, source bundles,
and bytecode values.

## Provider errors

`ProviderUnavailableError` covers credentials, transport, response decoding,
response validation, request scheduling, and retry exhaustion.

`ProviderRateLimitError` reports a short-window request limit. `ProviderQuotaError`
reports a daily, community, monthly, or similar quota. Both expose:

```python
error.provider
error.kind
error.detail
```

`ArtifactRetriever` records `ProviderError` messages in `RetrievalResult.errors`
and continues with the remaining providers. Direct provider calls raise them to
the caller.

## Reconciliation errors

`ArtifactConflictError` reports disagreement between providers on creation code,
runtime code, or source content.

## Cache errors

`CacheError` reports invalid cache format and cache I/O failures.

