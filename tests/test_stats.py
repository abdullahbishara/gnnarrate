from gnnarrate.stats import format_ci, mean_ci


def test_constant_values_have_zero_width_ci():
    assert mean_ci([0.5] * 10) == (0.5, 0.5, 0.5)


def test_none_safe():
    assert mean_ci([None, None]) == (None, None, None)
    mean, _, _ = mean_ci([0.2, None, 0.4])
    assert abs(mean - 0.3) < 1e-9


def test_ci_brackets_the_mean_and_stays_in_range():
    vals = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    mean, lo, hi = mean_ci(vals, seed=1)
    assert lo <= mean <= hi
    assert 0.0 <= lo and hi <= 1.0


def test_deterministic_under_seed():
    a = mean_ci([0.1, 0.3, 0.5, 0.7], seed=42)
    b = mean_ci([0.1, 0.3, 0.5, 0.7], seed=42)
    assert a == b


def test_format_ci_string():
    assert "0.500" in format_ci([0.5] * 5)
    assert format_ci([None]) == "n/a"
