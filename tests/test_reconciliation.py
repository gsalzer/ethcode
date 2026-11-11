from ethcode import SourceBundle, source_relation


def source(path, content):
    return SourceBundle("Solidity", {path: content}, "0.8.20", {"optimizer": {"enabled": False}})


def test_source_relations():
    assert source_relation(source("C.sol", "contract C {}\r\n"),
                           source("C.sol", "contract C {}\n")) == "line_endings"
    assert source_relation(source("C.sol", "contract C {}"),
                           source("src/C.sol", "contract C {}")) == "path_insensitive"
    assert source_relation(source("C.sol", "contract C{/*x*/}"),
                           source("C.sol", "contract C { }")) == "lexical"
    assert source_relation(source("C.sol", "contract C {}"),
                           source("C.sol", "contract D {}")) == "conflict"

