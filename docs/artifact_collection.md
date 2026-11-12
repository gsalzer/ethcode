# `ArtifactCollection`: Unreconciled provider claims

```python
ArtifactCollection(
    location: ContractLocation,
    requested_kinds: frozenset[ArtifactKind],
    observations: tuple[ProviderObservation, ...],
    failures: Mapping[str, ProviderFailure] = {},
)
```

The collection retains successful observations and failures without selecting
or merging artifacts. Requested kinds distinguish an unrequested artifact from
an authoritative absence or a provider failure. Every successful observation
must contain exactly the requested outcome keys.
