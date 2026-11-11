"""Populate the Sourcify response cache from a local Parquet dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Iterable

from ..cache import DEFAULT_CACHE_ROOT
from ..errors import ArtifactError
from ..models import ContractLocation
from ..providers import SourcifyProvider
from .addresses import read_addresses


TABLES = (
    "contract_deployments", "contracts", "code", "verified_contracts",
    "sourcify_matches", "compiled_contracts", "compiled_contracts_sources",
    "sources",
)


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            'Sourcify dataset import requires DuckDB; install "ethcode[dataset]"'
        ) from exc
    return duckdb


def _settings(value):
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        result = json.loads(value)
        if isinstance(result, dict):
            return result
    raise ValueError("dataset contains invalid compiler settings")


def fill_cache(dataset: Path, addresses: Iterable[ContractLocation], *,
               cache_dir: Path = DEFAULT_CACHE_ROOT / "sourcify",
               memory_limit: str = "2GB", temp_dir: Path | None = None) -> dict:
    """Import selected verified contracts without making API requests."""
    duckdb = _duckdb()
    dataset = Path(dataset).resolve()
    provider = SourcifyProvider(cache_dir, email="")
    requested = sorted(set(addresses), key=lambda item: (item.chain_id, item.address))
    pending = [location for location in requested if not provider.response_cached(location)]
    report = {
        "requested": len(requested),
        "already_cached": len(requested) - len(pending),
        "written": 0,
        "concurrently_cached": 0,
        "missing": [],
    }
    if not pending:
        return report

    files = {name: sorted((dataset / name).glob("*.parquet")) for name in TABLES}
    for name, paths in files.items():
        if not paths:
            raise ValueError(f"no Parquet files for {name} in {dataset}")
    before = {str(path): (path.stat().st_size, path.stat().st_mtime_ns)
              for paths in files.values() for path in paths}
    provenance = {"backend": "dataset", "path": str(dataset)}
    stats = dataset / "stats.json"
    if stats.exists():
        metadata = json.loads(stats.read_text(encoding="utf-8"))
        if isinstance(metadata, dict) and metadata.get("generatedAt") is not None:
            provenance["generated_at"] = metadata["generatedAt"]

    temporary_parent = str(temp_dir) if temp_dir is not None else None
    with tempfile.TemporaryDirectory(prefix="sourcify-import-",
                                     dir=temporary_parent) as scratch:
        db = duckdb.connect(str(Path(scratch) / "selected.duckdb"))
        try:
            db.execute("SET memory_limit = ?", [memory_limit])
            db.execute("SET temp_directory = ?", [str(Path(scratch) / "spill")])
            db.execute("SET preserve_insertion_order = false")
            for name, paths in files.items():
                db.read_parquet([str(path) for path in paths]).create_view(name)
            db.execute("CREATE TABLE wanted(chain_id BIGINT, address BLOB)")
            db.executemany("INSERT INTO wanted VALUES (?, ?)", [
                (location.chain_id, bytes.fromhex(location.address[2:]))
                for location in pending
            ])
            print(f"Selecting deployments for {len(pending)} addresses…", file=sys.stderr)
            db.execute("""CREATE TABLE deployments AS
                SELECT d.id, d.chain_id, d.address, d.contract_id, d.block_number
                FROM contract_deployments d JOIN wanted w USING (chain_id, address)""")
            db.execute("""CREATE TABLE verifications AS
                SELECT v.id, v.deployment_id, v.compilation_id FROM verified_contracts v
                JOIN deployments d ON d.id = v.deployment_id""")
            db.execute("""CREATE TABLE selected AS
                WITH latest AS (
                    SELECT id, verified_contract_id, creation_match, runtime_match, updated_at
                    FROM sourcify_matches
                    QUALIFY row_number() OVER (PARTITION BY id ORDER BY updated_at DESC,
                        verified_contract_id DESC) = 1
                )
                SELECT d.*, v.compilation_id, v.id AS verification_id,
                    m.id AS match_id, m.creation_match, m.runtime_match, m.updated_at
                FROM deployments d JOIN verifications v ON v.deployment_id = d.id
                JOIN latest m ON m.verified_contract_id = v.id
                WHERE m.creation_match IN ('perfect', 'partial', 'exact_match', 'match')
                   OR m.runtime_match IN ('perfect', 'partial', 'exact_match', 'match')
                QUALIFY row_number() OVER (PARTITION BY d.chain_id, d.address ORDER BY
                    d.block_number DESC NULLS LAST,
                    CASE WHEN m.runtime_match IN ('perfect', 'exact_match') THEN 2
                         WHEN m.runtime_match IN ('partial', 'match') THEN 1 ELSE 0 END DESC,
                    CASE WHEN m.creation_match IN ('perfect', 'exact_match') THEN 2
                         WHEN m.creation_match IN ('partial', 'match') THEN 1 ELSE 0 END DESC,
                    m.updated_at DESC, m.id DESC, v.id DESC, d.id) = 1""")
            print("Reading compilations, sources, and bytecode…", file=sys.stderr)
            db.execute("""CREATE TABLE selected_contracts AS
                SELECT c.id, c.creation_code_hash, c.runtime_code_hash FROM contracts c
                WHERE c.id IN (SELECT contract_id FROM selected)""")
            db.execute("""CREATE TABLE selected_code AS
                SELECT code_hash, code FROM code WHERE code_hash IN (
                    SELECT creation_code_hash FROM selected_contracts UNION
                    SELECT runtime_code_hash FROM selected_contracts)""")
            db.execute("""CREATE TABLE selected_compilations AS
                SELECT id, language, version, compiler, compiler_settings, name,
                    fully_qualified_name FROM compiled_contracts
                WHERE id IN (SELECT compilation_id FROM selected)""")
            db.execute("""CREATE TABLE source_paths AS
                SELECT compilation_id, source_hash, path FROM compiled_contracts_sources
                WHERE compilation_id IN (SELECT compilation_id FROM selected)""")
            db.execute("""CREATE TABLE selected_sources AS
                SELECT source_hash, content FROM sources
                WHERE source_hash IN (SELECT source_hash FROM source_paths)""")
            db.execute("CREATE INDEX code_lookup ON selected_code(code_hash)")
            db.execute("CREATE INDEX source_lookup ON selected_sources(source_hash)")
            db.execute("CREATE INDEX path_lookup ON source_paths(compilation_id)")

            after = {str(path): (path.stat().st_size, path.stat().st_mtime_ns)
                     for name in TABLES
                     for path in sorted((dataset / name).glob("*.parquet"))}
            if before != after:
                raise ValueError("dataset changed during import; stop syncing and rerun")

            rows = db.execute("""SELECT s.chain_id, s.address, s.compilation_id,
                    s.verification_id, s.match_id, s.creation_match, s.runtime_match,
                    c.language, c.version, c.compiler, c.compiler_settings,
                    c.name, c.fully_qualified_name, b.creation_code_hash, b.runtime_code_hash
                FROM selected s
                LEFT JOIN selected_compilations c ON c.id = s.compilation_id
                LEFT JOIN selected_contracts b ON b.id = s.contract_id
                ORDER BY s.chain_id, s.address""").fetchall()
            found: set[ContractLocation] = set()
            for row in rows:
                (chain, raw_address, compilation, verification, match_id,
                 creation_match, runtime_match, language, version, compiler,
                 settings, name, fully_qualified, creation_hash, runtime_hash) = row
                location = ContractLocation("0x" + raw_address.hex(), chain_id=chain)
                found.add(location)
                if language is None or runtime_hash is None:
                    raise ValueError(f"incomplete dataset joins for {chain}:{location.address}")
                sources = {}
                source_rows = db.execute("""SELECT p.path, s.content FROM source_paths p
                    LEFT JOIN selected_sources s USING (source_hash)
                    WHERE p.compilation_id = ? ORDER BY p.path""", [compilation]).fetchall()
                for path, content in source_rows:
                    if content is None or path in sources:
                        raise ValueError(
                            f"missing or duplicate source for {chain}:{location.address}: {path}")
                    sources[path] = {"content": content}
                if not sources:
                    raise ValueError(f"no sources for {chain}:{location.address}")

                def bytecode(code_hash):
                    if code_hash is None:
                        return None
                    code_row = db.execute(
                        "SELECT code FROM selected_code WHERE code_hash = ?", [code_hash]
                    ).fetchone()
                    if code_row is None or code_row[0] is None:
                        raise ValueError(f"missing bytecode for {chain}:{location.address}")
                    return "0x" + code_row[0].hex()

                def match_status(value):
                    return {"perfect": "exact_match", "partial": "match",
                            "exact_match": "exact_match", "match": "match"}.get(value)

                creation_match = match_status(creation_match)
                runtime_match = match_status(runtime_match)
                response = {
                    "chainId": str(chain),
                    "address": location.address,
                    "matchId": str(match_id),
                    "creationMatch": creation_match,
                    "runtimeMatch": runtime_match,
                    "match": ("exact_match" if "exact_match" in
                              (creation_match, runtime_match) else "match"),
                    "sources": sources,
                    "compilation": {
                        "language": language,
                        "compilerVersion": version,
                        "compiler": compiler,
                        "compilerSettings": _settings(settings),
                        "name": name,
                        "fullyQualifiedName": fully_qualified,
                    },
                    "creationBytecode": {"onchainBytecode": bytecode(creation_hash)},
                    "runtimeBytecode": {"onchainBytecode": bytecode(runtime_hash)},
                }
                written = provider.store_response(location, response, provenance={
                    **provenance,
                    "verification_id": str(verification),
                    "compilation_id": str(compilation),
                })
                report["written" if written else "concurrently_cached"] += 1
            report["missing"] = [
                {"chain": item.chain_id, "address": item.address}
                for item in pending if item not in found
            ]
        finally:
            db.close()
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Sourcify Parquet dataset directory")
    parser.add_argument("addresses", type=Path, help="CSV with chain,address columns")
    parser.add_argument("--cache-dir", type=Path,
                        default=DEFAULT_CACHE_ROOT / "sourcify")
    parser.add_argument("--memory-limit", default="2GB",
                        help="DuckDB memory limit (default: 2GB)")
    parser.add_argument("--temp-dir", type=Path,
                        help="parent for the temporary DuckDB database and spill files")
    parser.add_argument("--report", type=Path,
                        help="write the JSON report to this file instead of stdout")
    args = parser.parse_args(argv)
    try:
        report = fill_cache(
            args.dataset,
            read_addresses(args.addresses),
            cache_dir=args.cache_dir,
            memory_limit=args.memory_limit,
            temp_dir=args.temp_dir,
        )
        rendered = json.dumps(report, indent=2) + "\n"
        if args.report is None:
            print(rendered, end="")
        else:
            args.report.write_text(rendered, encoding="utf-8")
    except (ArtifactError, OSError, RuntimeError, ValueError,
            json.JSONDecodeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

