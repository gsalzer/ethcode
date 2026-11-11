# `EtherscanProvider`: Retrieve artifacts from Etherscan

```python
EtherscanProvider(
    cache_dir: Path = Path.home() / ".cache" / "ethcode" / "etherscan",
    api_key: str | None = None,
    *,
    calls_per_second: float = 3.0,
    timeout: float = 30,
)
```

The provider uses Etherscan API V2 to retrieve:

| Artifact | API action |
|---|---|
| Source | `contract/getsourcecode` |
| Creation code | `contract/getcontractcreation` |
| Runtime code | `proxy/eth_getCode` |

Only requested artifact kinds produce calls. Each endpoint response has an
independent cache entry, so a successful response remains reusable when another
endpoint fails.

## Credentials

Pass `api_key` or set `ETHERSCAN_API_KEY`:

```python
provider = EtherscanProvider(
    api_key="...",
)
```

Cached entries can be decoded without an API key.

The default cache directory is `~/.cache/ethcode/etherscan`. Pass `cache_dir`
to select another location.

## Request rate

`calls_per_second` defaults to 3. Calls are evenly spaced and coordinated by a
file lock and schedule file in the cache directory. Threads and processes using
that directory share the schedule and must use the same rate setting.

HTTP 429 and Etherscan rate-limit envelopes raise `ProviderRateLimitError`.
Daily, community, and other quota envelopes raise `ProviderQuotaError`. The
exception preserves the provider's result text in its `detail` attribute.

## Response classification

Successful source and bytecode values are normalized into `SourceBundle` and
`bytes`. The provider recognizes these absence forms:

- an empty source record;
- a source-not-verified API result;
- creation bytecode equal to `0x`;
- runtime bytecode equal to `0x`.

Recognized values and absences are cached. Operational and ambiguous responses
raise `ProviderUnavailableError` and remain retryable.

## Cache layout

```text
cache-root/
├── source/<chain-id>/<address>.json
├── creation/<chain-id>/<address>.json
├── runtime/<chain-id>/<address>.json
├── .request.lock
└── .request-schedule.json
```

Each artifact entry stores the raw response envelope and its `found` or
`not_found` classification. Cache reads repeat response normalization and verify
that the classification remains consistent.

