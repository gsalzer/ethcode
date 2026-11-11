# `ProviderObservation`: One provider result

```python
ProviderObservation(
    provider: str,
    location: ContractLocation,
    status: ObservationStatus,
    artifacts: ArtifactBundle = ArtifactBundle(),
    provenance: Mapping[str, JSONValue] = {},
    cached: bool = False,
)
```

`provider` is the stable provider name used by reconciliation and error reports.
`location` identifies the request, and `artifacts` contains the normalized values
returned for the requested kinds.

`provenance` records JSON-compatible provider context. The included providers
record their backend, cache classifications, and endpoint information. `cached`
is true when every response contributing to the observation came from cache.

## `ObservationStatus`

```python
ObservationStatus.FOUND
ObservationStatus.NOT_FOUND
```

`FOUND` indicates an accepted provider response for the contract. Artifact
fields show which requested values were available. `NOT_FOUND` indicates a
recognized provider absence and therefore accompanies an empty artifact bundle.

