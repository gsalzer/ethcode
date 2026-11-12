# Provider interface

Providers implement:

```python
class ArtifactProvider(Protocol):
    name: str
    def fetch(location, kinds) -> ProviderObservation: ...
```

A provider returns every requested kind as a found or absent outcome. An
exceptional endpoint failure raises `ProviderError` and returns no partial
observation. The collector retains expected provider/cache failures and
continues with the other configured provider.

Included providers are [`EtherscanProvider`](etherscan_provider.md) and
[`SourcifyProvider`](sourcify_provider.md).
