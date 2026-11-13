# Etherscan cache fill

`ethcode-fill-etherscan` retrieves source, creation bytecode, and runtime
bytecode from Etherscan for a list of contracts. Each outgoing endpoint
response is stored in the normal Etherscan cache.

## Command

```console
ethcode-fill-etherscan ADDRESSES [options]
```

`ADDRESSES` is a CSV file with `chain,address` columns:

```csv
chain,address
1,0xdAC17F958D2ee523a2206206994597C13D831ec7
11155111,0x2738d13E81e30bC615766A0410e7cF199FD59A83
```

The command reads the API key from `ETHERSCAN_API_KEY`. `--api-key VALUE` can
provide it explicitly.

Options:

- `--cache-dir PATH` selects the Etherscan cache directory; the default is
  `~/.cache/ethcode/etherscan`.
- `--calls-per-second RATE` sets the request rate; the default is `3`.
- `--timeout SECONDS` configures the HTTP timeout; the default is `30`.
- `--report PATH` writes the JSON report to a file instead of standard output.
- `--events PATH` appends one compact JSON event for every processed contract.
  Each line is flushed immediately and survives interruption. Repeated runs
  append new events with a distinct `run_id`.
- `--workers COUNT` retrieves several contracts concurrently. The default is
  `1`; use `3` to overlap typical network latency while the shared scheduler
  continues to cap request starts at `--calls-per-second`.

The cache-scoped schedule coordinates request starts across concurrent workers
and processes. Each request reserves the next slot using the caller's configured
rate. Network latency may overlap with later requests.

## Behavior

The command deduplicates and validates locations, requests every artifact kind,
and reports `found`, `not_found`, or `failed` for each contract. Cached endpoint
responses do not generate API calls. Rate-limit, quota, transport, and ambiguous
API errors are reported and remain uncached. Processing continues after ordinary
operational and rate-limit errors, but stops the current pass after a quota error;
rerunning later resumes from the endpoint responses already cached. If some
endpoint calls completed before another failed, their valid responses remain
cached and are reused on the next run.
For a long-running command, use unbuffered Python output for immediately visible
progress. The append-only event stream durably records successful, absent, and
failed observations even if the process is interrupted:

```console
python -u -m ethcode.tools.fill_etherscan_cache addresses.csv \
  --events etherscan-events.jsonl --report etherscan-report.json
```

## Python API

```python
from pathlib import Path

from ethcode.tools.addresses import read_addresses
from ethcode.tools.fill_etherscan_cache import fill_cache

locations = read_addresses(Path("addresses.csv"))
report = fill_cache(locations)
```
