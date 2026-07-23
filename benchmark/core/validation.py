"""Validator-side helpers used by every benchmark in `evals/`.

Every validator inspects the runtime variables the agent populated and
compares them against ground truth it recomputes from the source data.
This module exposes the three primitives that hand-off requires:

- `ValidatorResult`: the (success, message, variables_not_set) tuple that
  every `validate_*` returns.
- `is_finite_number`: NaN/None/bool/inf guard before any arithmetic.
- `compare_numeric`: signed numeric equality within tolerance (or implied
  tolerance from a `decimals=` precision). Validators must use this rather
  than hand-rolling `abs(a - b) > tol` — sign-erasing patterns slip in
  otherwise (see the helper's docstring).
"""

import math
from dataclasses import dataclass
from typing import Optional


try:
    import numpy as np
    _NUMPY_NUMERIC: tuple = (np.integer, np.floating)
except ImportError:
    _NUMPY_NUMERIC = ()


@dataclass
class ValidatorResult:
    """Return value of every `validate_*` in `evals/`.

    `variables_not_set` distinguishes "the agent didn't even populate the
    required runtime variables" (an infrastructure / refusal signal) from
    "the agent computed values but they're wrong" (a substantive failure).
    Downstream reporting in `scripts/run_stats.py` separates these.
    """

    success: bool
    message: str
    variables_not_set: bool = False


def is_finite_number(value) -> bool:
    """Return True iff `value` is a finite int/float (or numpy numeric).

    Rejects None, bool, NaN, +/-inf, strings, lists, and any non-numeric type.
    Use this as a NaN/None guard before any arithmetic comparison — without it,
    `abs(nan - x) > tol` is False, causing NaN to silently pass validation.
    """
    if value is None or isinstance(value, bool):
        return False
    if not isinstance(value, (int, float, *_NUMPY_NUMERIC)):
        return False
    return math.isfinite(float(value))


def compare_numeric(
    actual,
    expected,
    *,
    tolerance: Optional[float] = None,
    decimals: Optional[int] = None,
) -> bool:
    """Signed numeric equality within tolerance.

    Returns True iff `actual` is a finite number within tolerance of `expected`.
    Returns False (never raises) for None, NaN, +/-inf, bool, or non-numeric
    `actual` — so wrong-type and NaN agent outputs always fail validation.

    Use this in every validator instead of hand-rolling `abs(a - b) > tol`.
    Critically, this compares the **signed** difference: `+12` vs `-12` is
    a failure (≠), which is the correct behaviour for variables whose
    sign carries scientific meaning (jumps, declines, z-scores, year-over-
    year changes). Hand-rolled `abs(abs(a) - abs(b))` patterns erase signs
    and have caused real bugs in this repo — do not introduce new ones.

    Specify exactly one of `tolerance` or `decimals`:
      - tolerance=0.1     → absolute tolerance of ±0.1
      - decimals=2        → derives tolerance = 0.6 * 10^(-decimals) = 0.006,
                            i.e. the value must round to the same 2-dp number
                            as `expected` (within rounding-boundary slop)
    """
    if (tolerance is None) == (decimals is None):
        raise ValueError(
            "compare_numeric: pass exactly one of `tolerance=` or `decimals=`"
        )
    if tolerance is None:
        tolerance = 0.6 * (10 ** (-decimals))

    if not is_finite_number(expected):
        raise ValueError(
            f"compare_numeric: `expected` must be a finite number, got {expected!r}"
        )
    if not is_finite_number(actual):
        return False
    return abs(float(actual) - float(expected)) <= tolerance
