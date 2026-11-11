# `ArtifactKind`: Select artifacts

`ArtifactKind` is a string enumeration with three members:

```python
ArtifactKind.SOURCE     # "source"
ArtifactKind.CREATION   # "creation"
ArtifactKind.RUNTIME    # "runtime"
```

Pass a collection of members to `ArtifactRetriever.retrieve` or directly to a
provider:

```python
result = retriever.retrieve(
    location,
    kinds={ArtifactKind.CREATION, ArtifactKind.RUNTIME},
)
```

The default collection contains all three members. Etherscan makes and caches
one outgoing call for each selected kind. Sourcify derives the selected kinds
from its single contract response.

