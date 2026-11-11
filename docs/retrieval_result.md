# `RetrievalResult`: Combined retrieval outcome

```python
RetrievalResult(
    location: ContractLocation,
    artifacts: ArtifactBundle,
    observations: tuple[ProviderObservation, ...],
    reconciliation: ReconciliationReport,
    errors: Mapping[str, str] = {},
)
```

`ArtifactRetriever.retrieve` returns this model.

- `location` is the requested contract.
- `artifacts` is the reconciled bundle.
- `observations` contains successful provider observations.
- `reconciliation` records contributors and source selection.
- `errors` maps providers to operational error messages.

```python
result = retriever.retrieve(location)

for observation in result.observations:
    print(observation.provider, observation.status, observation.cached)

for provider, message in result.errors.items():
    print(provider, message)
```

Provider errors allow reconciliation to proceed with the remaining observations.
Artifact disagreement raises `ArtifactConflictError` while constructing the
result.

