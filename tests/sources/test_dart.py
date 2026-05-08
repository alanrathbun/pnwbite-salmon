from datetime import date
from pathlib import Path
from sources.dart import parse_dart_curve, daily_average_for, RuntimingCurve

FIXTURE = Path(__file__).parent.parent / "fixtures/dart/sample_curve.csv"


def test_parse_returns_dict_keyed_by_doy():
    csv_text = FIXTURE.read_text()
    curve = parse_dart_curve(csv_text)
    assert isinstance(curve, RuntimingCurve)
    # Chinook 10-yr avg at Bonneville is blank for many winter days (~65 missing).
    # We accept >=280 as "most of the year is covered".
    assert len(curve.daily_avg) >= 280
    # Day-of-year keys are ints from 1 to 365 or 366.
    assert min(curve.daily_avg) >= 1
    assert max(curve.daily_avg) <= 366


def test_curve_has_a_peak():
    csv = FIXTURE.read_text()
    curve = parse_dart_curve(csv)
    peak_doy = max(curve.daily_avg, key=lambda k: curve.daily_avg[k])
    # Spring chinook at Bonneville peaks roughly day 110-130 (mid-Apr to early May)
    # Summer chinook peaks around 180-200 (early-mid July)
    # Fall chinook peaks 240-265 (early-mid September)
    # Just assert *some* meaningful peak (>0) inside the year.
    assert curve.daily_avg[peak_doy] > 0


def test_daily_average_for_specific_date():
    csv = FIXTURE.read_text()
    curve = parse_dart_curve(csv)
    val = daily_average_for(curve, date(2026, 4, 27))
    assert val is not None and val >= 0
