# `ArtifactCollector`: Collect provider observations

```python
ArtifactCollector(providers)
collection = collector.collect(location, kinds=tuple(ArtifactKind))
```

The collector accepts one or more providers with unique names. It validates the
request, calls each provider independently, and returns an `ArtifactCollection`.
Documented provider and cache failures are retained as `ProviderFailure` values;
programming errors and invalid provider return values propagate.

An exceptional endpoint failure produces no partial observation for that
provider. Endpoint responses completed before the failure remain cached.
