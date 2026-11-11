# `ContractLocation`: Identify a deployed contract

```python
ContractLocation(address: str, chain_id: int = 1)
```

A contract location consists of a positive EVM chain ID and a 20-byte address.
Ethereum mainnet, chain ID 1, is the default.

```python
from ethcode import ContractLocation

mainnet = ContractLocation(
    "0xdAC17F958D2ee523a2206206994597C13D831ec7"
)
sepolia = ContractLocation(
    "0x2738d13E81e30bC615766A0410e7cF199FD59A83",
    chain_id=11155111,
)
```

Addresses use the `0x` prefix followed by exactly 40 hexadecimal characters.
Construction normalizes the address to lowercase. Invalid addresses and chain
IDs raise `InvalidArtifactError`.

The model is frozen and supports equality and hashing through normal dataclass
semantics.

