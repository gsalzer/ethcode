# Errors

`InvalidArtifactError` reports invalid caller input or invalid model values.
`ProviderError` carries structured provider failure context. Specialized
`ProviderRateLimitError` and `ProviderQuotaError` retain limit classification.
`CacheError` reports unreadable or malformed cache entries.

`ArtifactCollector` converts documented provider and cache errors into frozen
`ProviderFailure` models. Programming errors and violated provider invariants
propagate. Comparison reports provider disagreement as data rather than raising
a reconciliation exception.
