# `SourceBundle`: Compiler source input

```python
SourceBundle(
    language: str,
    sources: Mapping[str, str],
    version: str | None = None,
    settings: Mapping[str, JSONValue] | None = None,
)
```

`language` names the compiler language, such as `Solidity`, `Vyper`, or `Yul`.
`sources` maps each compiler source-unit path to its text content. `version` and
`settings` retain compiler metadata supplied by the provider.

```python
source = SourceBundle(
    language="Solidity",
    version="0.8.20+commit.a1b79de6",
    sources={"contracts/C.sol": "contract C {}"},
    settings={"optimizer": {"enabled": False}},
)
```

Language and sources must be nonempty. Every path must be a nonempty string and
every source value must be text. Invalid values raise `InvalidArtifactError`.

Source-unit paths remain part of the bundle because they affect compiler input
and the source relations used during reconciliation.

