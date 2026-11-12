# `ArtifactKind`: Select requested artifacts

```python
ArtifactKind.SOURCE
ArtifactKind.CREATION
ArtifactKind.RUNTIME
```

Pass a nonempty collection of members to `ArtifactCollector.collect()` or a
provider. The default requests all three kinds.
