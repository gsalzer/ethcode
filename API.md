# API reference

The collection and comparison interface is exported from `ethcode`:

```python
from ethcode import ArtifactCollector, ContractLocation, ArtifactKind, compare
```

Providers are exported from `ethcode.providers`:

```python
from ethcode.providers import EtherscanProvider, NodeProvider, SourcifyProvider
```

## Collection

### [`ArtifactCollector`](docs/artifact_collector.md)

```python
ArtifactCollector(providers: Iterable[ArtifactProvider])

collect(
    location: ContractLocation,
    *,
    kinds: Collection[ArtifactKind] = tuple(ArtifactKind),
) -> ArtifactCollection
```

The collector accepts one or more uniquely named providers.

### [`ArtifactCollection`](docs/artifact_collection.md)

Contains the location, requested kinds, successful observations, and structured
failures.

### [`ContractLocation`](docs/contract_location.md)

```python
ContractLocation(address: str, chain_id: int = 1)
```

### [`ArtifactKind`](docs/artifact_kind.md)

```python
ArtifactKind.SOURCE
ArtifactKind.CREATION
ArtifactKind.RUNTIME
```

## Observation models

- [`ProviderObservation`](docs/provider_observation.md) contains one provider's
  per-kind outcomes and provenance.
- [`ArtifactOutcome`](docs/artifact_outcome.md) records `found` or authoritative
  `absent`, the value when found, and cache status.
- [`ProviderFailure`](docs/provider_failure.md) records typed, safe failure
  context.
- [`SourceBundle`](docs/source_bundle.md) preserves source text, paths,
  language, version, and settings.
- [`ArtifactBundle`](docs/artifact_bundle.md) is a computed view of artifacts
  found in one observation.

## Comparison

### [`compare`](docs/comparison.md)

```python
compare(collection: ArtifactCollection) -> ComparisonAnalysis
```

Comparison is pure and returns conflicts as data. Bytecode comparisons expose a
consensus value when one value is available or all available values agree, and
`None` when values differ.

`ComparisonAnalysis` contains an optional `SourceComparison` and optional
`BytecodeComparison` values for the requested kinds.

## Providers

### [`EtherscanProvider`](docs/etherscan_provider.md)

```python
EtherscanProvider(
    cache_dir=Path.home() / ".cache" / "ethcode" / "etherscan",
    api_key=None,
    *, calls_per_second=3.0, timeout=30,
    ssl_context=None, ca_file=None,
)
```

### [`SourcifyProvider`](docs/sourcify_provider.md)

```python
SourcifyProvider(
    cache_dir=Path.home() / ".cache" / "ethcode" / "sourcify",
    email=None,
    *, timeout=30, interval=1.0, retries=3, backoff=2.0,
    max_wait=60.0, project_url="https://github.com/gsalzer/ethcode",
    ssl_context=None, ca_file=None,
)
```

### `NodeProvider`

```python
NodeProvider(cache_dir)
```

Reads optional creation and runtime `.hex` files without network access. It
does not supply source code.

All providers implement the [`ArtifactProvider`](docs/providers.md) protocol. Cache
semantics are described in [Caching](docs/caching.md), and typed failures in
[Errors](docs/errors.md).

## Cache tools

- [`ethcode-fill-etherscan`](docs/etherscan_fill.md)
- [`ethcode-fill-sourcify`](docs/sourcify_dataset.md)
