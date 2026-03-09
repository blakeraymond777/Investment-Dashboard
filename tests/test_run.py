
import pytest
from unittest.mock import patch, MagicMock


import finance_utils
import db_utils
import data_scraping_utils


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_finance_utils_globals():
    """Reset all mutable finance_utils.py globals before each test."""
    finance_utils.START_TIME = None
    finance_utils.END_TIME = None
    finance_utils.FUNDS = {}
    finance_utils.COMPANIES_TO_SEARCH = dict.fromkeys(finance_utils.COMPANIES_TO_SEARCH_KEYS, 0.0)
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
    finance_utils.FUNDS = {}
    finance_utils.calculate_company_exposures_for_fund("MISSING", 100)
    assert all(v == 0.0 for v in finance_utils.COMPANIES_TO_SEARCH.values())


def test_exposures_uses_cached_nport():
    finance_utils.FUNDS = {"VFIAX": SAMPLE_NPORT}
    finance_utils.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    finance_utils.calculate_company_exposures_for_fund("VFIAX", 100)

    assert finance_utils.COMPANIES_TO_SEARCH["Amazon.com Inc"] == pytest.approx(250.0)


def test_exposures_fetches_nport_when_none_in_cache():
    finance_utils.FUNDS = {"VFIAX": None}
    finance_utils.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    with patch("finance_utils.data_scraping_utils.fetch_nport_from_sec_url", return_value=SAMPLE_NPORT) as mock_fetch, \
         patch("finance_utils.db_utils.update_existing_fund") as mock_update:
        finance_utils.calculate_company_exposures_for_fund("VFIAX", 100)

    mock_fetch.assert_called_once_with("VFIAX")
    mock_update.assert_called_once()
    assert finance_utils.COMPANIES_TO_SEARCH["Amazon.com Inc"] == pytest.approx(250.0)


def test_exposures_returns_early_when_fetch_fails():
    finance_utils.FUNDS = {"VFIAX": None}
    finance_utils.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    with patch("finance_utils.data_scraping_utils.fetch_nport_from_sec_url", return_value=None):
        finance_utils.calculate_company_exposures_for_fund("VFIAX", 100)

    assert finance_utils.COMPANIES_TO_SEARCH["Amazon.com Inc"] == 0.0


def test_exposures_unmatched_company_stays_zero():
    finance_utils.FUNDS = {"VFIAX": SAMPLE_NPORT}
    finance_utils.COMPANIES_TO_SEARCH = {"Netflix": 0.0}

    finance_utils.calculate_company_exposures_for_fund("VFIAX", 1000)

    assert finance_utils.COMPANIES_TO_SEARCH["Netflix"] == 0.0


def test_exposures_accumulates_across_multiple_funds():
    finance_utils.FUNDS = {"VFIAX": SAMPLE_NPORT, "FXAIX": SAMPLE_NPORT}
    finance_utils.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}

    finance_utils.calculate_company_exposures_for_fund("VFIAX", 100)
    finance_utils.calculate_company_exposures_for_fund("FXAIX", 200)

    # 2.5 * 100 + 2.5 * 200 = 750
    assert finance_utils.COMPANIES_TO_SEARCH["Amazon.com Inc"] == pytest.approx(750.0)


# ─────────────────────────────────────────────
# timer()
# ─────────────────────────────────────────────

def test_timer_sets_start_time_on_first_call():
    finance_utils.timer()
    assert finance_utils.START_TIME is not None
    assert finance_utils.END_TIME is None


def test_timer_sets_end_time_on_second_call():
    finance_utils.timer()
    finance_utils.timer()
    assert finance_utils.END_TIME is not None
    assert finance_utils.END_TIME >= finance_utils.START_TIME


# ─────────────────────────────────────────────
# determine_portfolio_exposure()
# ─────────────────────────────────────────────

@patch("finance_utils.db_utils.connect")
@patch("finance_utils.db_utils.load_user_portfolio", return_value=[("VFIAX", 1000)])
@patch("finance_utils.db_utils.load_funds_from_cache", return_value={"VFIAX": None})
@patch("finance_utils.data_scraping_utils.fetch_nport_from_sec_url", return_value=None)
def test_portfolio_exposure_handles_missing_nport(*_):
    finance_utils.COMPANIES_TO_SEARCH = {"Amazon.com Inc": 0.0}
    finance_utils.determine_portfolio_exposure()
    assert finance_utils.COMPANIES_TO_SEARCH["Amazon.com Inc"] == 0.0


@patch("finance_utils.db_utils.connect")
@patch("finance_utils.db_utils.load_user_portfolio", return_value=[("VFIAX", 100), ("VFIAX", 200)])
@patch("finance_utils.db_utils.load_funds_from_cache", return_value={"VFIAX": None})
@patch("finance_utils.data_scraping_utils.fetch_nport_from_sec_url", return_value=None)
def test_portfolio_exposure_flattens_duplicate_fund_entries(_, mock_load_funds, __, ___):
    finance_utils.determine_portfolio_exposure()
    # Flattening is correct if load_funds_from_cache received ["VFIAX"] once, not twice
    tickers_requested = mock_load_funds.call_args[0][0]
    assert tickers_requested == ["VFIAX"]
