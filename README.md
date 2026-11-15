# ethcode

`ethcode` collects smart-contract source, creation bytecode, and runtime
bytecode from Etherscan, Sourcify, and local node-cache files. It caches validated provider responses,
retains structured outcomes and failures, and compares representations without
selecting canonical artifacts.

## Installation

```console
python -m pip install "git+https://github.com/gsalzer/ethcode.git"
```

For development:

```console
git clone https://github.com/gsalzer/ethcode.git
cd ethcode
python -m pip install -e ".[test]"
```

Python 3.10 or newer is required.

## Usage

```python
from ethcode import ArtifactCollector, ContractLocation, compare
from ethcode.providers import EtherscanProvider, NodeProvider, SourcifyProvider

collector = ArtifactCollector([
    EtherscanProvider(),
    SourcifyProvider(),
    NodeProvider("cache/node"),
])
collection = collector.collect(
    ContractLocation("0xdAC17F958D2ee523a2206206994597C13D831ec7")
)
analysis = compare(collection)
```

`collection` contains each successful provider observation and each structured
provider failure. `analysis` describes source and exact bytecode relations. It
does not merge or select artifacts.

Ethereum mainnet, chain ID 1, is the default. Pass another positive chain ID to
`ContractLocation` for another EVM chain.

## Provider configuration

Etherscan reads `ETHERSCAN_API_KEY` and defaults to three calls per second.
Sourcify reads `SOURCIFY_EMAIL`. The HTTP providers accept explicit credentials,
cache directories, timeouts, SSL contexts, or CA files.

`NodeProvider` reads optional creation and runtime bytecode from
`<cache>/creation/<chain>/<address>.hex` and
`<cache>/runtime/<chain>/<address>.hex`. It performs no network access and
does not provide source code.

The default cache parent is `~/.cache/ethcode`. Provider caches coordinate
request timing across processes sharing the same cache directory. Cached
responses can be used without credentials.

## Package boundary

`ethcode` performs provider communication, caching, normalization, collection,
and descriptive comparison. Callers own reconciliation, artifact selection,
compilation, semantic bytecode checks, and artifact storage.

## Cache-filling commands

Retrieve all artifact kinds from Etherscan for a CSV with `chain,address`
columns:

```console
ethcode-fill-etherscan addresses.csv
```

Import selected records from a local Sourcify Parquet dataset:

```console
python -m pip install "ethcode[dataset]"
ethcode-fill-sourcify /path/to/parquet addresses.csv
```

See [Etherscan cache fill](docs/etherscan_fill.md) and
[Sourcify dataset import](docs/sourcify_dataset.md).

## Documentation

See [API.md](API.md) for the public API and links to individual descriptions.

## Testing

```console
python -m pytest
```
