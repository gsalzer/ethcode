# `SourcifyProvider`: Retrieve artifacts from Sourcify

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

The provider queries Sourcify API V2 at
`/contract/{chainId}/{address}`. One response supplies source, creation code, and
runtime code. The request selects the source, compilation, and on-chain bytecode
fields used to construct the artifact bundle.

## Contact information

Pass `email` or set `SOURCIFY_EMAIL`. The provider includes the package name,
project URL, and email in its User-Agent:

```python
provider = SourcifyProvider(
    email="research@example.org",
)
```

Cached responses can be decoded without contact configuration.

The default cache directory is `~/.cache/ethcode/sourcify`. Pass `cache_dir`
to select another location.

## Cache import methods

```python
response_cached(location: ContractLocation) -> bool
```

Returns whether a validated response envelope exists in the contract cache.

```python
store_response(
    location: ContractLocation,
    response: dict,
    *,
    provenance: dict | None = None,
) -> bool
```

Validates and stores an API-shaped successful contract response when the entry
is absent. It returns `True` when it writes and `False` when an entry already
exists. The [Sourcify dataset importer](sourcify_dataset.md) uses this method.


## Retry behavior

Requests are serialized across processes using the same cache directory.
`interval` supplies the normal cooldown. HTTP 429 and 5xx responses use
exponential backoff controlled by `retries` and `backoff`. A `Retry-After`
header extends the cooldown. `max_wait` bounds the time accepted from a shared
cooldown record.

## Response validation

For a successful contract response, the provider checks:

- chain ID and address match the request;
- verification match fields contain recognized values;
- source and compilation fields form a valid `SourceBundle`;
- creation and runtime code are valid hexadecimal byte strings.

A recognized 404 response produces a `NOT_FOUND` observation. Valid successful
and absence responses are cached as raw provider responses.

## Cache layout

```text
cache-root/
├── contract/<chain-id>/<address>.json
├── .request.lock
└── .cooldown.json
```

Sourcify's contract endpoint is intended for individual lookups. Sourcify's
Parquet and BigQuery datasets serve bulk collection workloads.

