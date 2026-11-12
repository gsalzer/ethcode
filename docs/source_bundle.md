# `SourceBundle`: Lossless compiler source input

```python
SourceBundle(language, sources, version=None, settings=None)
```

`sources` maps exact provider paths to exact source text. Paths, contents, line
endings, language, version, and settings are retained without normalization.
Comparison applies temporary documented normalizations without modifying the
bundle.
