# `compare`: Describe provider relations

```python
analysis = compare(collection)
```

Comparison is pure, does not rewrite provider observations, and returns
disagreements as data.

`BytecodeComparison.relation` is `equal`, `different`, or `unavailable`.
`providers` identifies every provider that supplied the artifact. `value` is
the sole available bytecode, the shared bytecode when all available values are
identical, or `None` when no value is available or values differ. Original
provider bytecodes and provenance remain in `ArtifactCollection.observations`.

`SourceComparison` reports content, normalized language, compiler version, and
settings relations separately. Content relations are `exact`, `line_endings`,
`path_insensitive`, `lexical`, or `conflict`. Settings report shared,
complementary, and conflicting dotted paths; lists are compared as complete
values and booleans remain distinct from integers.
