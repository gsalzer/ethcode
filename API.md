# API reference

The main public API is available directly from `ethcode`:

```python
from ethcode import ArtifactRetriever, ContractLocation, ArtifactKind
```

Provider implementations are exported from `ethcode.providers`:

```python
from ethcode.providers import EtherscanProvider, SourcifyProvider
```

## Retrieval

### [`ArtifactRetriever`](docs/artifact_retriever.md)

```python
ArtifactRetriever(
    providers: Iterable[ArtifactProvider],
    *,
    policy: ReconciliationPolicy | None = None,
)
```

Queries one or more providers and reconciles their observations.

```python
retrieve(
    location: ContractLocation,
    *,
    kinds: Collection[ArtifactKind] = tuple(ArtifactKind),
) -> RetrievalResult
```

### [`ContractLocation`](docs/contract_location.md)

```python
ContractLocation(address: str, chain_id: int = 1)
```

Identifies a deployed contract. Addresses are validated and normalized to
lowercase.

### [`ArtifactKind`](docs/artifact_kind.md)

```python
ArtifactKind.SOURCE
ArtifactKind.CREATION
ArtifactKind.RUNTIME
```

Selects the artifacts requested from each provider.

## Providers

### [`EtherscanProvider`](docs/etherscan_provider.md)

```python
EtherscanProvider(
    cache_dir: Path = Path.home() / ".cache" / "ethcode" / "etherscan",
    api_key: str | None = None,
    *,
    calls_per_second: float = 3.0,
    timeout: float = 30,
)
```

Retrieves source, creation code, and runtime code through separate Etherscan V2
calls and caches each response independently.

### [`SourcifyProvider`](docs/sourcify_provider.md)

```python
SourcifyProvider(
    cache_dir: Path = Path.home() / ".cache" / "ethcode" / "sourcify",
    email: str | None = None,
    *,
    timeout: float = 30,
    interval: float = 1.0,
    retries: int = 3,
    backoff: float = 2.0,
    max_wait: float = 60.0,
    project_url: str = "https://github.com/gsalzer/ethcode",
)
```

Retrieves a Sourcify verified-contract record and derives the requested artifacts.

Both providers implement the [`ArtifactProvider`](docs/providers.md) protocol.

## Artifact and result models

An overview is available in [Artifact and result models](docs/models.md).

### [`SourceBundle`](docs/source_bundle.md)

```python
SourceBundle(
    language: str,
    sources: Mapping[str, str],
    version: str | None = None,
    settings: Mapping[str, JSONValue] | None = None,
)
```

### [`ArtifactBundle`](docs/artifact_bundle.md)

```python
ArtifactBundle(
    source: SourceBundle | None = None,
    creation_code: bytes | None = None,
    runtime_code: bytes | None = None,
)
```

### [`ProviderObservation`](docs/provider_observation.md)

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

### [`RetrievalResult`](docs/retrieval_result.md)

```python
RetrievalResult(
    location: ContractLocation,
    artifacts: ArtifactBundle,
    observations: tuple[ProviderObservation, ...],
    reconciliation: ReconciliationReport,
    errors: Mapping[str, str] = {},
)
```

### [`ObservationStatus`](docs/provider_observation.md)

```python
ObservationStatus.FOUND
ObservationStatus.NOT_FOUND
```

## Reconciliation

### [`ReconciliationPolicy`](docs/reconciliation_policy.md)

```python
ReconciliationPolicy(
    preferred_source_providers: tuple[str, ...] = ("sourcify", "etherscan"),
    source_selector: Callable | None = None,
)
```

### [`source_relation`](docs/source_relation.md)

```python
source_relation(left: SourceBundle, right: SourceBundle) -> str
```

Returns `exact`, `line_endings`, `path_insensitive`, `lexical`, or `conflict`.

## Cache behavior

Provider cache layout, concurrency, and cacheability rules are described in
[Caching](docs/caching.md).

## Cache filling and dataset import

The [`ethcode-fill-etherscan`](docs/etherscan_fill.md) command retrieves all
artifact kinds for a list of contracts. Its reusable Python entry point is:

```python
fill_cache(
    addresses: Iterable[ContractLocation],
    *,
    cache_dir: Path = Path.home() / ".cache" / "ethcode" / "etherscan",
    api_key: str | None = None,
    calls_per_second: float = 3.0,
    timeout: float = 30,
) -> dict
```

The [`ethcode-fill-sourcify`](docs/sourcify_dataset.md) command populates the
Sourcify response cache from the Parquet dataset. Its reusable Python entry
points are:

```python
read_addresses(path: Path) -> list[ContractLocation]

fill_cache(
    dataset: Path,
    addresses: Iterable[ContractLocation],
    *,
    cache_dir: Path = Path.home() / ".cache" / "ethcode" / "sourcify",
    memory_limit: str = "2GB",
    temp_dir: Path | None = None,
) -> dict
```

## Exceptions

The exception hierarchy and retry semantics are described in
[Errors](docs/errors.md).

