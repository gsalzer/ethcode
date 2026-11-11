# Sourcify dataset import

`ethcode-fill-sourcify` populates the Sourcify response cache from selected
contracts in a local Sourcify Parquet dataset.

Install the dataset extra:

```console
python -m pip install "ethcode[dataset]"
```

For an editable checkout:

```console
python -m pip install -e ".[dataset,test]"
```

## Command

```console
ethcode-fill-sourcify DATASET ADDRESSES [options]
```

`DATASET` contains the unpacked Sourcify Parquet tables. `ADDRESSES` is a CSV
file with `chain,address` columns:

```csv
chain,address
1,0xdAC17F958D2ee523a2206206994597C13D831ec7
11155111,0x2738d13E81e30bC615766A0410e7cF199FD59A83
```

Options:

- `--cache-dir PATH` selects the Sourcify cache directory; the default is
  `~/.cache/ethcode/sourcify`.
- `--memory-limit VALUE` sets the DuckDB memory limit; the default is `2GB`.
- `--temp-dir PATH` selects a parent for the temporary DuckDB database and spill files.
- `--report PATH` writes the JSON report to a file instead of standard output.

## Behavior

The importer:

1. Deduplicates and validates requested locations.
2. Skips locations with an existing cache response.
3. Selects the strongest and latest verification for each deployment.
4. Reconstructs the source, compilation, creation, and runtime fields returned by Sourcify API V2.
5. Validates each response through `SourcifyProvider.store_response`.
6. Preserves cache entries created by concurrent processes.
7. Reports requested, cached, written, concurrently cached, and missing counts.

Dataset misses remain eligible for later API lookup. The importer verifies that
the Parquet files stay unchanged while it reads them.

## Python API

```python
from pathlib import Path

from ethcode.tools.addresses import read_addresses
from ethcode.tools.fill_sourcify_cache import fill_cache

locations = read_addresses(Path("addresses.csv"))
report = fill_cache(Path("sourcify-parquet"), locations)
```

DuckDB is imported when `fill_cache` starts. Other `ethcode` functionality and
the command's `--help` output are available without the dataset extra.

