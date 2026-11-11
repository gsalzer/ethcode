# `ReconciliationPolicy`: Combine provider observations

```python
ReconciliationPolicy(
    preferred_source_providers: tuple[str, ...] = ("sourcify", "etherscan"),
    source_selector: Callable | None = None,
)
```

The policy requires exact equality among all supplied creation bytecode values
and among all supplied runtime bytecode values. A disagreement raises
`ArtifactConflictError`.

Source bundles can differ by an accepted representation relation. The default
provider preference selects Sourcify before Etherscan. Change the tuple to use a
different fixed order:

```python
policy = ReconciliationPolicy(
    preferred_source_providers=("etherscan", "sourcify"),
)
```

`source_selector` receives the available `(provider_name, SourceBundle)` pairs
and returns the provider name to select. It takes precedence over the preference
tuple.

`reconcile(observations)` returns an `ArtifactBundle` and a
`ReconciliationReport`. The report maps artifact kinds to contributors and
records the accepted source relation and selected source provider.

