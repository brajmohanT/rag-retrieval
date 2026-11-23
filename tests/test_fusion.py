import pytest

from evidence_atlas.retrieval.fusion import rrf


def test_hand_calculated_rrf():
    a = {1: ["X", "Y", "Z"]}
    b = {1: ["Y", "W"]}
    fused = dict(rrf([a, b], k=10)[1])
    # Y: 1/(10+2) + 1/(10+1); X: 1/(10+1); W: 1/(10+2); Z: 1/(10+3)
    assert fused["Y"] == pytest.approx(1 / 12 + 1 / 11)
    assert [page for page, _ in rrf([a, b], k=10)[1]] == ["Y", "X", "W", "Z"]


def test_weights_and_k_change_the_vote():
    a, b = {1: ["X", "Y"]}, {1: ["Y", "X"]}
    assert rrf([a, b], weights=[2, 1])[1][0][0] == "X"
    assert rrf([a, b], weights=[1, 2])[1][0][0] == "Y"


def test_question_missing_from_one_method_and_depth():
    fused = rrf([{1: ["X"], 2: ["P", "Q"]}, {1: ["Y"]}], depth=1)
    assert set(fused) == {1, 2}
    assert [page for page, _ in fused[2]] == ["P"]
