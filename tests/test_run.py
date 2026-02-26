
import pytest
from unittest.mock import patch, MagicMock


import run


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_run_globals():
    """Reset all mutable run.py globals before each test."""
    run.START_TIME = None
    run.END_TIME = None
    run.FUNDS = {}
    run.COMPANIES_TO_SEARCH = dict.fromkeys(run.COMPANIES_TO_SEARCH_KEYS, 0.0)
    yield


SAMPLE_NPORT = """
<invstOrSec>
    <n>Amazon.com Inc</n>
    <pctVal>2.5</pctVal>
</invstOrSec>
<invstOrSec>
    <n>Apple Inc</n>
    <pctVal>7.0</pctVal>
</invstOrSec>
"""


# ─────────────────────────────────────────────
# calculate_company_exposures_for_fund()
# ─────────────────────────────────────────────

def test_exposures_skips_fund_not_in_funds_dict():
    run.FUNDS = {}
    run.calculate_company_exposures_for_fund("MISSING", 100)
    assert all(v == 0.0 for v in run.COMPANIES_TO_SEARCH.values())


def test_exposures_uses_cached_nport():
    run.FUNDS = {"VFIAX": SAMPLE_NPORT}
    run.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    run.calculate_company_exposures_for_fund("VFIAX", 100)

    assert run.COMPANIES_TO_SEARCH["Amazon.com Inc"] == pytest.approx(250.0)


def test_exposures_fetches_nport_when_none_in_cache():
    run.FUNDS = {"VFIAX": None}
    run.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    with patch("run.data_utils.fetch_nport_from_sec_url", return_value=SAMPLE_NPORT) as mock_fetch, \
         patch("run.data_utils.update_existing_fund") as mock_update:
        run.calculate_company_exposures_for_fund("VFIAX", 100)

    mock_fetch.assert_called_once_with("VFIAX")
    mock_update.assert_called_once()
    assert run.COMPANIES_TO_SEARCH["Amazon.com Inc"] == pytest.approx(250.0)


def test_exposures_returns_early_when_fetch_fails():
    run.FUNDS = {"VFIAX": None}
    run.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    with patch("run.data_utils.fetch_nport_from_sec_url", return_value=None):
        run.calculate_company_exposures_for_fund("VFIAX", 100)

    assert run.COMPANIES_TO_SEARCH["Amazon.com Inc"] == 0.0


def test_exposures_unmatched_company_stays_zero():
    run.FUNDS = {"VFIAX": SAMPLE_NPORT}
    run.COMPANIES_TO_SEARCH = {"Netflix": 0.0}

    run.calculate_company_exposures_for_fund("VFIAX", 1000)

    assert run.COMPANIES_TO_SEARCH["Netflix"] == 0.0


def test_exposures_accumulates_across_multiple_funds():
    run.FUNDS = {"VFIAX": SAMPLE_NPORT, "FXAIX": SAMPLE_NPORT}
    run.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    run.calculate_company_exposures_for_fund("VFIAX", 100)
    run.calculate_company_exposures_for_fund("FXAIX", 200)

    # 2.5 * 100 + 2.5 * 200 = 750
    assert run.COMPANIES_TO_SEARCH["Amazon.com Inc"] == pytest.approx(750.0)


# ─────────────────────────────────────────────
# timer()
# ─────────────────────────────────────────────

def test_timer_sets_start_time_on_first_call():
    run.timer()
    assert run.START_TIME is not None
    assert run.END_TIME is None


def test_timer_sets_end_time_on_second_call():
    run.timer()
    run.timer()
    assert run.END_TIME is not None
    assert run.END_TIME >= run.START_TIME


# ─────────────────────────────────────────────
# determine_portfolio_exposure()
# ─────────────────────────────────────────────

@patch("run.data_utils.connect")
@patch("run.data_utils.load_user_portfolio", return_value=[("VFIAX", 1000)])
@patch("run.data_utils.load_funds_from_cache", return_value={"VFIAX": None})
@patch("run.data_utils.fetch_nport_from_sec_url", return_value=None)
def test_portfolio_exposure_handles_missing_nport(*_):
    run.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}
    run.determine_portfolio_exposure()
    assert run.COMPANIES_TO_SEARCH["Amazon.com Inc"] == 0.0


@patch("run.data_utils.connect")
@patch("run.data_utils.load_user_portfolio", return_value=[("VFIAX", 100), ("VFIAX", 200)])
@patch("run.data_utils.load_funds_from_cache", return_value={"VFIAX": None})
@patch("run.data_utils.fetch_nport_from_sec_url", return_value=None)
def test_portfolio_exposure_flattens_duplicate_fund_entries(_, mock_load_funds, __, ___):
    run.determine_portfolio_exposure()
    # Flattening is correct if load_funds_from_cache received ["VFIAX"] once, not twice
    tickers_requested = mock_load_funds.call_args[0][0]
    assert tickers_requested == ["VFIAX"]
