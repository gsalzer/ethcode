from ethcode import (
    ArtifactCollection, ArtifactKind, ArtifactOutcome, ContractLocation,
    FailureCategory, FailureOrigin, OutcomeStatus, ProviderFailure,
    ProviderObservation, SourceBundle, compare,
)
import copy


LOCATION = ContractLocation("0x" + "12" * 20)


def observation(name, source, runtime=b"\x00"):
    return ProviderObservation(name, LOCATION, {
        ArtifactKind.SOURCE: ArtifactOutcome(OutcomeStatus.FOUND, source),
        ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.FOUND, runtime),
    })


def source(path, content, settings=None):
    return SourceBundle("Solidity", {path: content}, "0.8.20", settings)


def analysis(left, right):
    collection = ArtifactCollection(
        LOCATION,
        frozenset({ArtifactKind.SOURCE, ArtifactKind.RUNTIME}),
        (observation("sourcify", right), observation("etherscan", left)),
    )
    return compare(collection)


def test_source_content_relations_are_independent_of_registration_order():
    assert analysis(source("C.sol", "contract C {}\r\n"),
                    source("C.sol", "contract C {}\n")).source.content_relation == "line_endings"
    result = analysis(source("C.sol", "contract C {}"),
                      source("src/C.sol", "contract C {}"))
    assert result.source.providers == ("etherscan", "sourcify")
    assert result.source.content_relation == "path_insensitive"
    assert analysis(source("C.sol", "contract C{/*x*/}"),
                    source("C.sol", "contract C { }")).source.content_relation == "lexical"


def test_complementary_and_conflicting_settings_are_descriptive():
    complementary = analysis(
        source("C.sol", "contract C {}", {"optimizer": {"enabled": True}}),
        source("C.sol", "contract C {}", {
            "optimizer": {"enabled": True, "runs": 200}}),
    ).source
    assert complementary.settings_relation == "complementary"
    assert complementary.shared_settings == ("optimizer.enabled",)
    assert complementary.complementary_settings == ("optimizer.runs",)

    conflict = analysis(
        source("C.sol", "contract C {}", {"optimizer": {"runs": 100}}),
        source("C.sol", "contract C {}", {"optimizer": {"runs": 200}}),
    ).source
    assert conflict.settings_relation == "conflict"
    assert conflict.conflicting_settings == ("optimizer.runs",)


def test_bytecode_difference_is_data_not_exception():
    result = analysis(source("C.sol", "contract C {}"),
                      source("C.sol", "contract C {}"))
    assert result.runtime.relation == "equal"

    collection = ArtifactCollection(
        LOCATION, frozenset({ArtifactKind.RUNTIME}),
        (ProviderObservation("one", LOCATION, {
            ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.FOUND, b"\x00")}),
         ProviderObservation("two", LOCATION, {
            ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.FOUND, b"\x01")})),
    )
    assert compare(collection).runtime.relation == "different"


def test_bytecode_comparison_uses_all_available_providers():
    def runtime(name, value):
        return ProviderObservation(name, LOCATION, {
            ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.FOUND, value),
        })

    equal = ArtifactCollection(
        LOCATION, frozenset({ArtifactKind.RUNTIME}),
        (runtime("one", b"\x00"), runtime("two", b"\x00"),
         runtime("three", b"\x00")),
    )
    assert compare(equal).runtime.relation == "equal"
    assert compare(equal).runtime.providers == ("one", "three", "two")

    different = ArtifactCollection(
        LOCATION, frozenset({ArtifactKind.RUNTIME}),
        (runtime("one", b"\x00"), runtime("two", b"\x00"),
         runtime("three", b"\x01")),
    )
    assert compare(different).runtime.relation == "different"


def test_settings_empty_boolean_and_list_semantics():
    empty = analysis(source("C.sol", "contract C {}", None),
                     source("C.sol", "contract C {}", {})).source
    assert empty.settings_relation == "exact"

    boolean = analysis(
        source("C.sol", "contract C {}", {"optimizer": {"enabled": True}}),
        source("C.sol", "contract C {}", {"optimizer": {"enabled": 1}}),
    ).source
    assert boolean.conflicting_settings == ("optimizer.enabled",)

    lists = analysis(
        source("C.sol", "contract C {}", {"remappings": ["a=b"]}),
        source("C.sol", "contract C {}", {"remappings": ["a=b", "c=d"]}),
    ).source
    assert lists.conflicting_settings == ("remappings",)


def test_comparison_preserves_raw_source_representation():
    left = source("C.sol", "contract C {}\r\n", {"optimizer": {"enabled": True}})
    right = source("src/C.sol", "contract C {}\n", {
        "optimizer": {"enabled": True, "runs": 200}})
    originals = copy.deepcopy((left, right))
    analysis(left, right)
    assert (left, right) == originals


def test_absence_and_provider_failure_make_comparison_unavailable():
    found = ProviderObservation("one", LOCATION, {
        ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.FOUND, b"\x00")})
    absent = ProviderObservation("two", LOCATION, {
        ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.ABSENT)})
    collection = ArtifactCollection(
        LOCATION, frozenset({ArtifactKind.RUNTIME}), (found, absent))
    result = compare(collection).runtime
    assert result.relation == "unavailable"
    assert result.providers == ("one",)

    failure = ProviderFailure(
        "two", FailureCategory.TIMEOUT, "timeout", True, FailureOrigin.REQUEST,
        failed_kind=ArtifactKind.RUNTIME)
    collection = ArtifactCollection(
        LOCATION, frozenset({ArtifactKind.RUNTIME}), (found,), {"two": failure})
    assert compare(collection).runtime.relation == "unavailable"
