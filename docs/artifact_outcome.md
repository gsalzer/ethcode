# `ArtifactOutcome`: One requested artifact result

```python
ArtifactOutcome(
    status: OutcomeStatus,
    value: SourceBundle | bytes | None = None,
    cached: bool = False,
)
```

`OutcomeStatus.FOUND` requires a value. `OutcomeStatus.ABSENT` is an
authoritative provider absence and has no value. Absence is a successful
endpoint outcome rather than a failure. `cached` reports whether the endpoint
response came from the provider cache.
