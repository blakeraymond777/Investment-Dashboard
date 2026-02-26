
import pytest
from unittest.mock import patch, MagicMock

import data_utils


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def mock_conn():
    """A mock DB connection with a pre-attached mock cursor."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ─────────────────────────────────────────────
# connect()
# ─────────────────────────────────────────────

def test_connect_uses_correct_filename():
    with patch("data_utils.sqlite3.connect") as mock_sqlite:
        mock_sqlite.return_value = MagicMock()
        result = data_utils.connect()
        mock_sqlite.assert_called_once_with("finance_data.db")
        assert result is mock_sqlite.return_value

# ─────────────────────────────────────────────
# fetch_nport_from_sec_url()
# ─────────────────────────────────────────────

def test_fetch_nport_returns_none_when_no_url_in_db():
    with patch("run.data_utils.get_sec_url", return_value=None):
        result = data_utils.fetch_nport_from_sec_url("UNKNOWN")
    assert result is None


def test_fetch_nport_fetches_and_returns_text():
    mock_response = MagicMock()
    mock_response.text = "<nport>data</nport>"

    with patch("run.data_utils.get_sec_url", return_value="http://sec.gov/test"), \
         patch("data_utils.os.getenv", return_value="test@example.com"), \
         patch("data_utils.requests.get", return_value=mock_response) as mock_get:
        result = data_utils.fetch_nport_from_sec_url("VFIAX")

    assert result == "<nport>data</nport>"
    mock_get.assert_called_once()

# ─────────────────────────────────────────────
# load_funds_from_cache()
# ─────────────────────────────────────────────

def test_load_funds_returns_dict(mock_conn):
    rows = [("VFIAX", "<nport/>"), ("FXAIX", "<nport/>")]
    mock_conn.cursor().fetchall.return_value = rows

    result = data_utils.load_funds_from_cache(["VFIAX", "FXAIX"], existing_connection=mock_conn)

    assert result == dict(rows)


def test_load_funds_returns_empty_dict_for_unknown_tickers(mock_conn):
    mock_conn.cursor().fetchall.return_value = []

    result = data_utils.load_funds_from_cache(["UNKNOWN"], existing_connection=mock_conn)

    assert result == {}


def test_load_funds_creates_connection_when_none_given():
    mock_conn = MagicMock()
    mock_conn.cursor().fetchall.return_value = []

    with patch("data_utils.connect", return_value=mock_conn) as mock_connect:
        data_utils.load_funds_from_cache(["VFIAX"])
        mock_connect.assert_called_once()


# ─────────────────────────────────────────────
# load_user_portfolio()
# ─────────────────────────────────────────────

def test_load_user_portfolio_returns_rows(mock_conn):
    rows = [("VFIAX", 1000), ("FXAIX", 500)]
    mock_conn.cursor().fetchall.return_value = rows

    result = data_utils.load_user_portfolio(1, existing_connection=mock_conn)

    mock_conn.cursor().execute.assert_called_once_with(
        "SELECT fund, amount FROM portfolios WHERE user = ?", (1,)
    )
    assert result == rows


def test_load_user_portfolio_returns_empty_for_unknown_user(mock_conn):
    mock_conn.cursor().fetchall.return_value = []

    result = data_utils.load_user_portfolio(999, existing_connection=mock_conn)

    assert result == []


# ─────────────────────────────────────────────
# update_existing_fund()
# ─────────────────────────────────────────────

def test_update_fund_raises_on_none_ticker():
    with pytest.raises(ValueError):
        data_utils.update_existing_fund(None)


def test_update_fund_no_op_when_no_fields_given(mock_conn):
    data_utils.update_existing_fund("VFIAX", existing_connection=mock_conn)
    mock_conn.cursor().execute.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("sec_url", "http://new.url"),
    ("nport_document", "<nport/>"),
])
def test_update_fund_generates_correct_sql(mock_conn, field, value):
    kwargs = {field: value, "existing_connection": mock_conn}
    data_utils.update_existing_fund("VFIAX", **kwargs)

    query = mock_conn.cursor().execute.call_args[0][0]
    assert "UPDATE funds SET" in query
    assert field in query


def test_update_fund_closes_internally_created_connection():
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = MagicMock()

    with patch("data_utils.connect", return_value=mock_conn):
        data_utils.update_existing_fund("VFIAX", sec_url="http://x.com")

    mock_conn.close.assert_called_once()


def test_update_fund_does_not_close_external_connection(mock_conn):
    data_utils.update_existing_fund("VFIAX", sec_url="http://x.com", existing_connection=mock_conn)
    mock_conn.close.assert_not_called()


# ─────────────────────────────────────────────
# get_sec_url()
# ─────────────────────────────────────────────

def test_get_sec_url_returns_url_when_found(mock_conn):
    mock_conn.cursor().fetchone.return_value = ("VFIAX", "http://sec.gov/test")

    result = data_utils.get_sec_url("VFIAX", existing_connection=mock_conn)

    assert result == "http://sec.gov/test"


def test_get_sec_url_returns_none_when_not_found(mock_conn):
    mock_conn.cursor().fetchone.return_value = None

    result = data_utils.get_sec_url("UNKNOWN", existing_connection=mock_conn)

    assert result is None


# ─────────────────────────────────────────────
# delete_table()
# ─────────────────────────────────────────────

def test_delete_table_drops_named_table(mock_conn):
    data_utils.delete_table("portfolios", existing_connection=mock_conn)
    mock_conn.cursor().execute.assert_called_once_with("DROP TABLE IF EXISTS portfolios")


def test_delete_table_skips_when_none(mock_conn):
    data_utils.delete_table(None, existing_connection=mock_conn)
    mock_conn.cursor().execute.assert_not_called()


# ─────────────────────────────────────────────
# delete_user_portfolio()
# ─────────────────────────────────────────────

def test_delete_user_portfolio_raises_on_none_user():
    with pytest.raises(ValueError):
        data_utils.delete_user_portfolio(None)


def test_delete_user_portfolio_executes_query(mock_conn):
    data_utils.delete_user_portfolio(1, existing_connection=mock_conn)
    mock_conn.cursor().execute.assert_called_once()
