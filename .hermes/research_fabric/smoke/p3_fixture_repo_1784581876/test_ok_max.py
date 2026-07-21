from ok_max import safe_max

def test_max():
    assert safe_max([3, 1, 2]) == 3
    assert safe_max([], default=-1) == -1
    assert safe_max([]) is None
