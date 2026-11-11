# `ArtifactRetriever`: Retrieve and reconcile artifacts

```python
ArtifactRetriever(
    providers: Iterable[ArtifactProvider],
    *,
    policy: ReconciliationPolicy | None = None,
)
```

`ArtifactRetriever` queries each configured provider for the same contract and
combines their observations under a reconciliation policy. At least one provider
is required, and provider names must be unique.

## `retrieve`

```python
retrieve(
    location: ContractLocation,
    *,
    kinds: Collection[ArtifactKind] = tuple(ArtifactKind),
) -> RetrievalResult
```

By default, retrieval requests source, creation code, and runtime code. Pass a
set of artifact kinds to select a subset:

```python
from ethcode import ArtifactKind

result = retriever.retrieve(
    location,
    kinds={ArtifactKind.RUNTIME},
)
```

Each provider produces a `ProviderObservation`. A `ProviderError` is recorded in
`RetrievalResult.errors` under the provider name, and retrieval continues with
the remaining providers. An observation must carry the configured provider name
and requested location.

Reconciliation requires creation and runtime bytecode returned by multiple
providers to agree exactly. Source representations are compared using
`source_relation`. A disagreement raises `ArtifactConflictError`.

## Result inspection

```python
result.artifacts          # reconciled ArtifactBundle
result.observations       # successful provider observations
result.reconciliation     # contributors and source selection
result.errors             # provider name -> error message
```

An empty artifact bundle can result when every provider reports absence or an
operational error. The observations and errors distinguish those cases.

