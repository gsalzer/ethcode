# `EtherscanProvider`

Etherscan API V2 supplies source, creation bytecode, and current runtime
bytecode through independent endpoint calls and cache entries. The provider
reads `ETHERSCAN_API_KEY`, defaults to three calls per second, and coordinates
request spacing across processes using the same cache directory.

The constructor accepts `cache_dir`, `api_key`, `calls_per_second`, `timeout`,
`ssl_context`, and `ca_file`. An explicit SSL context and CA file are mutually
exclusive; `SSL_CERT_FILE` is respected by default.

Plain source records conservatively preserve optimizer status and runs, EVM
version, compiler metadata, contract name, and source filename. Recognized
unverified or empty values become absent outcomes. Successful and authoritative
absence envelopes are cached; operational and malformed responses are not.

JSON-shaped source accepts both Solidity Standard JSON with a top-level
`sources` member and direct path-to-source maps. Source-map entries may be text
or objects containing text in `content`; paths and contents are retained
exactly.
