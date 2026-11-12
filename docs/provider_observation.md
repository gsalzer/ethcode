# `ProviderObservation`: One provider's claims

```python
ProviderObservation(
    provider: str,
    location: ContractLocation,
    outcomes: Mapping[ArtifactKind, ArtifactOutcome],
    provenance: Mapping[str, JSONValue] = {},
)
```

Per-kind outcomes are authoritative. `artifacts` and `cached` are computed
properties. Provenance contains provider metadata and backend context but does
not participate implicitly in comparison.
