# Provider interface

Providers implement the structural `ArtifactProvider` protocol:

```python
class ArtifactProvider(Protocol):
    name: str

    def fetch(
        self,
        location: ContractLocation,
        kinds: Collection[ArtifactKind],
    ) -> ProviderObservation: ...
```

`name` identifies the provider in observations, reconciliation reports, and
errors. Names in one `ArtifactRetriever` must be unique.

`fetch` returns artifacts for the requested location and kinds. The observation
contains:

- provider identity;
- contract location;
- `FOUND` or `NOT_FOUND` status;
- normalized artifacts;
- provider-specific provenance;
- whether every contributing response came from cache.

Provider implementations raise subclasses of `ProviderError` for configuration,
transport, response, cache, rate-limit, and quota failures. The retriever records
these failures and continues with other providers.

The included implementations are:

- [`EtherscanProvider`](etherscan_provider.md)
- [`SourcifyProvider`](sourcify_provider.md)

