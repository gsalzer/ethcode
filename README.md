# ethcode

`ethcode` is a Python package for retrieving smart-contract source, creation
bytecode, and runtime bytecode from Etherscan and Sourcify. It caches provider
responses, records their provenance, and reconciles artifacts returned by
multiple providers.

## Installation

Install the latest version directly from GitHub:

```console
python -m pip install "git+https://github.com/gsalzer/ethcode.git"
```

For development, clone the repository and install it in editable mode:

```console
git clone https://github.com/gsalzer/ethcode.git
cd ethcode
python -m pip install -e ".[test]"
```

Install the optional DuckDB support for Sourcify dataset imports with:

```console
python -m pip install "ethcode[dataset]"
```

Python 3.10 or newer is required.

## Basic usage

```python
from ethcode import ArtifactRetriever, ContractLocation
from ethcode.providers import EtherscanProvider, SourcifyProvider

retriever = ArtifactRetriever([
    EtherscanProvider(),
    SourcifyProvider(),
])
result = retriever.retrieve(
    ContractLocation("0xdAC17F958D2ee523a2206206994597C13D831ec7")
)

source = result.artifacts.source
creation_code = result.artifacts.creation_code
runtime_code = result.artifacts.runtime_code
```

Ethereum mainnet, chain ID 1, is the default. Pass another positive chain ID for
another EVM chain:

```python
location = ContractLocation("0x...", chain_id=11155111)
```

## Provider configuration

Etherscan reads its API key from `ETHERSCAN_API_KEY`, or accepts it explicitly.
The default request rate is three calls per second:

```python
etherscan = EtherscanProvider(
    api_key="...",
    calls_per_second=3,
)
```

Sourcify uses a contact email in its User-Agent. Set `SOURCIFY_EMAIL`, or pass
the address explicitly:

```python
sourcify = SourcifyProvider(
    email="research@example.org",
)
```

The default cache parent is `~/.cache/ethcode`, with `etherscan` and `sourcify`
subdirectories. Pass `cache_dir=Path(...)` to either provider to select another
location.

Provider caches coordinate request timing across threads and processes that use
the same cache directory. Cached responses can be read without credentials.

## Entry points

### Retrieval

- `ArtifactRetriever` — query providers and reconcile their observations.
- `ContractLocation` — identify a contract by chain ID and address.
- `ArtifactKind` — select source, creation code, or runtime code.

### Providers

- `EtherscanProvider` — retrieve individual artifacts through Etherscan API V2.
- `SourcifyProvider` — retrieve a verified-contract record through Sourcify API V2.

### Results

- `RetrievalResult` — combined artifacts, observations, reconciliation, and errors.
- `ArtifactBundle` — normalized source and bytecode values.
- `SourceBundle` — language, compiler version, settings, and source files.
- `ProviderObservation` — one provider's normalized response and provenance.

### Reconciliation

- `ReconciliationPolicy` — require bytecode agreement and select equivalent source.
- `source_relation` — classify the relationship between two source bundles.

See [API.md](API.md) for the complete API reference and links to detailed guides.

## Caching

The cache stores validated responses from individual outgoing calls. Etherscan
source, creation, and runtime endpoints have separate entries. One Sourcify
contract response supplies all three artifact kinds. Successful responses and
recognized absences are cached; operational failures remain retryable.

### Etherscan cache fill

`ethcode-fill-etherscan` retrieves source, creation bytecode, and runtime
bytecode for contracts listed in a CSV file:

```console
ethcode-fill-etherscan addresses.csv
```

The CSV contains `chain,address` columns. The command uses
`ETHERSCAN_API_KEY` by default, observes the provider's shared rate limit, and
reports results and errors for each contract. See
[Etherscan cache fill](docs/etherscan_fill.md) for all options.

### Sourcify dataset import

`ethcode-fill-sourcify` preloads selected contracts from Sourcify's Parquet
dataset into the normal Sourcify response cache:

```console
ethcode-fill-sourcify /path/to/parquet addresses.csv
```

The CSV contains `chain,address` columns. Existing cache entries are preserved,
and addresses absent from the dataset are reported without creating absence
entries. See [Sourcify dataset import](docs/sourcify_dataset.md) for options and
dataset layout.

## Testing

Run the test suite from the repository root:

```console
python -m pytest
```

