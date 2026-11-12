# `ArtifactBundle`: Computed provider artifact view

`ArtifactBundle` contains optional source, creation code, and runtime code.
`ProviderObservation.artifacts` computes this view from found per-kind outcomes.
It represents one provider only and is never a reconciled or canonical bundle.

`empty()` reports whether every field is absent.
