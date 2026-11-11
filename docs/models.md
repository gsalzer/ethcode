# Artifact and result models

The public models are frozen dataclasses. Bytecode values use `bytes`, source
files map compiler input paths to text, and provenance values are JSON-compatible.

- [`ContractLocation`](contract_location.md) identifies a deployed contract.
- [`ArtifactKind`](artifact_kind.md) selects requested artifacts.
- [`SourceBundle`](source_bundle.md) holds compiler source input.
- [`ArtifactBundle`](artifact_bundle.md) holds normalized source and bytecode.
- [`ProviderObservation`](provider_observation.md) records one provider result.
- [`RetrievalResult`](retrieval_result.md) combines provider observations.

