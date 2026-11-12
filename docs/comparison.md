# `compare`: Describe provider relations

```python
analysis = compare(collection)
```

Comparison is pure and supports at most two successful observations. It does
not select, merge, or rewrite artifacts and returns disagreements as data.

`BytecodeComparison.relation` is `equal`, `different`, or `unavailable`.
`SourceComparison` reports content, normalized language, compiler version, and
settings relations separately. Content relations are `exact`, `line_endings`,
`path_insensitive`, `lexical`, or `conflict`. Settings report shared,
complementary, and conflicting dotted paths; lists are compared as complete
values and booleans remain distinct from integers.
