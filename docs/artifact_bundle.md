# `ArtifactBundle`: Normalized contract artifacts

```python
ArtifactBundle(
    source: SourceBundle | None = None,
    creation_code: bytes | None = None,
    runtime_code: bytes | None = None,
)
```

The fields are independently optional:

- `source` contains compiler source units and settings.
- `creation_code` contains deployment initcode.
- `runtime_code` contains deployed code.

Bytecode values are nonempty `bytes`. Providers remove transport hexadecimal
encoding before constructing the bundle.

```python
if result.artifacts.runtime_code is not None:
    print(result.artifacts.runtime_code.hex())
```

`empty()` returns `True` when every field is absent.

