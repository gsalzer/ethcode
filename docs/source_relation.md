# `source_relation`: Compare source representations

```python
source_relation(left: SourceBundle, right: SourceBundle) -> str
```

The function returns the strongest recognized relationship between two source
bundles:

| Result | Meaning |
|---|---|
| `exact` | Bundles are equal. |
| `line_endings` | Source paths match after newline normalization. |
| `path_insensitive` | Source contents match as a multiset after newline normalization. |
| `lexical` | Source token multisets match after comments and whitespace are removed. |
| `conflict` | No accepted relationship holds. |

Language comparisons are case-insensitive. Compiler version and settings must
agree before representation-level comparison proceeds.

The lexical relation preserves string literals and token boundaries while
discarding whitespace and complete line or block comments. An unterminated block
comment remains a token and therefore participates in comparison.

`ReconciliationPolicy` uses this function before selecting one provider's source
representation.

