import csv
import requests
import os
import re
import json
import db_utils
from dotenv import load_dotenv
import time
from urllib.parse import parse_qs, urlparse


FUND_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{acc}.txt"

# NPORT-P = public monthly-portfolio filing, NPORT-P/A = its amendment
NPORT_FORMS = ("NPORT-P", "NPORT-P/A")

_REQUEST_DELAY = 0.15  # seconds between calls, keeps us well under SEC's 10 req/s
_COMPANY_FILING_SUFFIXES = ("the", "grp", "group", "svcs", "services", "cos", "companies", "reit")

### Helpers ###
def _build_request_headers():
    load_dotenv()
    email = os.getenv("USER_AGENT_EMAIL")
    if not email:
        raise RuntimeError("Set USER_AGENT_EMAIL in your .env (SEC requires a contact in the User-Agent).")
    return {"User-Agent": f"PersonalInvestmentApp {email}"}

def _sanitize_company(name):
    name = re.sub(r"[.,]|\b(inc|incorporated|corp|corporation|ltd|llc|-|holdings)\b| /(new|adr|de)/?",
                  "", name.casefold())
    name = re.sub(r"/.*?/", "", name.replace("&", "and").replace(" ", ""))
    name = re.sub(r"/adr|/de", "", name)
    name = name.removesuffix("new").removesuffix("/")
    name = re.sub(r"/.{2,3}$", "", name)
    name = re.sub(r"[()]|holdings|hldgs", "", name)
    for suffix in _COMPANY_FILING_SUFFIXES:
        name = name.removesuffix(suffix)
    return name

def _parse_cik(cik):
    """Accepts a CIK such as 1067839, '1067839', or '0001067839'."""
    s = str(cik).strip()
    if s.isdigit():
        return int(s)
    raise ValueError(f"Invalid CIK: {cik!r}")

_TICKER_CACHE = {}
# TODO remove/consolidate? - replace with logic to check local DB first 
def _load_ticker_maps():
    """Download SEC's ticker maps once per process."""
    if _TICKER_CACHE:
        return _TICKER_CACHE
    # Mutual funds + ETFs: rows of [cik, seriesId, classId, symbol]
    response = requests.get(FUND_TICKERS_URL, headers=_build_request_headers())
    response.raise_for_status()
    mf = response.json()

    fields = mf["fields"]
    i_cik, i_series, i_sym = fields.index("cik"), fields.index("seriesId"), fields.index("symbol")
    _TICKER_CACHE["mf"] = {
        row[i_sym].upper(): (int(row[i_cik]), row[i_series]) for row in mf["data"] if row[i_sym]
    }
    return _TICKER_CACHE

# TODO only need to check for funds, companies don't have NPORTs
def _resolve_ticker(ticker):
    """
    Map a fund ticker (VFIAX, QQQ, ...) to (cik, series_id).
    series_id is None when only the general company-ticker map knows the symbol.
    """
    t = ticker.strip().upper()
    maps = _load_ticker_maps()
    if t in maps["mf"]:
        return maps["mf"][t]
    raise LookupError(f"Ticker {ticker!r} not found in SEC's fund ticker files")

def _looks_like_ticker(s):
    s = str(s).strip()
    return bool(s) and not s.isdigit() and "/" not in s and "?" not in s

def _build_txt_url(cik, accession):
    """Full-submission .txt URL for an accession number like 0000036405-26-000063."""
    return ARCHIVES_URL.format(cik=int(cik), acc_nodash=accession.replace("-", ""), acc=accession)

def _rows_from_block(block):
    """Turn the column-oriented 'recent' block of the submissions JSON into row dicts."""
    keys = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
    cols = {k: block.get(k, []) for k in keys}
    n = len(cols["accessionNumber"])
    return [{k: (cols[k][i] if i < len(cols[k]) else "") for k in keys} for i in range(n)]

# determine the sec url to use for the fund by checking local and then programmatically searching EDGAR if needed
def fetch_nport_from_sec_url(fund_ticker):
    # check if we have a url already but are just missing the nport
    url = db_utils.get_sec_url(fund_ticker)
    # TODO: if we don't have a url, try to get it from EDGAR (integrate)
    if url is None:
        print(f"No SEC url to check for {fund_ticker}")
        return None

    # Fetch the file
    headers = _build_request_headers()
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.text

def fetch_data_to_populate_funds():
    response = requests.get(FUND_TICKERS_URL, headers=_build_request_headers())
    response.raise_for_status()
    
    return response.json()["data"]

def fetch_data_to_populate_companies(url):
    if not url:
        response = requests.get(COMPANY_TICKERS_URL, headers=_build_request_headers())
    else:
        response = requests.get(url, headers=_build_request_headers())
    response.raise_for_status()
    data = response.text

    # Check if we are looking at an NPORT doc
    fund_investments = re.findall(r'<invstOrSec>.*?</invstOrSec>', data, re.DOTALL)

    # Otherwise, we are looking at the company tickers JSON, so return it unfiltered
    if fund_investments == []:
        return data

    # [ name, title, lei, cusip ]
    all_funds = []
    for fund_position in fund_investments:
        this_fund = []

        name = re.search(r'<name>(.*?)</name>', fund_position)
        if name: 
            if name.group(1) == 'N/A': continue
            this_fund.append(name.group(1))

        title = re.search(r'<title>(.*?)</title>', fund_position)
        if title: this_fund.append(title.group(1))

        lei = re.search(r'<lei>(.*?)</lei>', fund_position)
        if lei: this_fund.append(lei.group(1))

        cusip = re.search(r'<cusip>(.*?)</cusip>', fund_position)
        if cusip: this_fund.append(cusip.group(1))

        all_funds.append(this_fund)

    return all_funds

def fetch_company_data():
        # Vanguard - VFIAX
        url_vanguard = "https://www.sec.gov/Archives/edgar/data/36405/000003640526000063/0000036405-26-000063.txt"

        # Fidelity - FXAIX
        url_fidelity = "https://www.sec.gov/Archives/edgar/data/819118/000003540225001329/0000035402-25-001329.txt"

        # Load fund composition data
        all_vanguard_fund_companies = fetch_data_to_populate_companies(url_vanguard)
        all_fidelity_fund_companies = fetch_data_to_populate_companies(url_fidelity)

        # Start with list of companies in fidelity fund and merge in new values from vanguard's fund
        # These lists should be almost identical (they are both tracking the S&P 500)
        if all_fidelity_fund_companies:
            merged_companies = list(all_fidelity_fund_companies).copy()
            if all_vanguard_fund_companies:
                for v_fund in all_vanguard_fund_companies:
                    overlap_flag = False
                    for f_fund in all_fidelity_fund_companies:
                        # Match names/titles to each other or leis
                        if (v_fund[0].casefold() == f_fund[0].casefold() or
                            v_fund[0].casefold() == f_fund[1].casefold() or
                            v_fund[1].casefold() == f_fund[1].casefold() or
                            v_fund[1].casefold() == f_fund[0].casefold() or
                            (len(v_fund) > 2 and len(f_fund) > 2) or v_fund[3] == f_fund[3] ): 
                                overlap_flag = True
                                break
                    # Found a company in the Vanguard fund that was not in the Fidelity fund
                    if not overlap_flag:
                        merged_companies.append(v_fund)
        else: 
            merged_companies = list(all_vanguard_fund_companies).copy()

        print(f"Found {len(merged_companies)} companies within Vanguard/Fidelity S&P500 funds\n")
        # filter out "N/A" values - use empty string "" instead
        merged_companies = [["" if item == "N/A" else item for item in row] for row in merged_companies]

        # Scrape a large list of SEC-registered companies and their tickers/CIK values and parse into JSON
        # {"cik_str", "ticker", "title"}
        company_scraped_data = fetch_data_to_populate_companies(COMPANY_TICKERS_URL)
        if company_scraped_data:
            all_companies = json.loads(str(company_scraped_data))

            match_count = 0
            for company in merged_companies:
                # sanitize name and title for the sake of matching
                name = _sanitize_company(company[0])
                title = _sanitize_company(company[1])

                for item in all_companies.values():
                    all_search = _sanitize_company(item["title"])

                    if all_search in (name, title):
                        match_count += 1
                        company.append(item["ticker"])
                        # prepend zeroes to pad to length 10 for all 
                        company.append(str(item["cik_str"]).zfill(10))
                        break
            
            print(f"Successfully linked {match_count} company tickers and CIKs ({int(match_count/len(merged_companies)*100)}%) to representations in funds\n")

        else:
            print("Could not load SEC-registered company data\n")

        # [ name, title, lei, cusip, ticker, cik ]
        # pad with empty strings if we did not find the company ticker/CIK from the fund
        merged_companies = [row + [""] * (6 - len(row)) for row in merged_companies]
        
        # write the company data to a csv
        print(f"Writing company data to CSV")
        with open("scraped_companies.csv", "w", newline="") as f:
            writer = csv.writer(f)

            # write the header row and then all of the company data
            writer.writerow(["Name", "Title", "LEI", "CUSIP", "Ticker", "CIK"])
            writer.writerows(merged_companies)

def list_nport_filings(cik):
    """All NPORT-P / NPORT-P/A filings for a CIK, newest first."""
    cik = _parse_cik(cik)
    url = SUBMISSIONS_URL.format(cik=str(cik).zfill(10))
    response = requests.get(url, headers=_build_request_headers())
    response.raise_for_status()
    data = response.json()

    filings = _rows_from_block(data.get("filings", {}).get("recent", {}))
    found = [f for f in filings if f["form"] in NPORT_FORMS]

    # Older history lives in extra JSON files; only pull them if recent had nothing.
    if not found:
        for extra in data.get("filings", {}).get("files", []):
            url = SUBMISSIONS_FILE_URL.format(name=extra["name"])
            time.sleep(_REQUEST_DELAY)
            response = requests.get(url, headers=_build_request_headers())
            response.raise_for_status()
            block = response.json()
            found += [f for f in _rows_from_block(block) if f["form"] in NPORT_FORMS]

    found.sort(key=lambda f: (f["filingDate"], f["accessionNumber"]), reverse=True)
    return found

# TODO remove/consolidate error handling - don't fail if not found
def fetch_latest_nport_txt(url_or_cik, series_id=None, max_candidates=25):
    """
    Return (txt_url, filing_dict, text) for the newest N-PORT filing.

    A trust (e.g. Fidelity, Vanguard) files one N-PORT per series under the same
    registrant CIK, so the newest filing may belong to a different fund. Pass
    `series_id` (e.g. 'S000002839') to walk back through filings until the one
    whose <seriesId> matches is found.
    """
    # TODO remove/consolidate?
    if _looks_like_ticker(url_or_cik):
        cik, resolved_series = _resolve_ticker(url_or_cik)
        series_id = series_id or resolved_series  # narrow to this fund's series automatically
    else:
        cik = _parse_cik(url_or_cik)
    filings = list_nport_filings(cik)
    if not filings:
        raise LookupError(
            f"No NPORT-P filings found for CIK {cik}. Some products (e.g. unit investment trusts) are not required to file N-PORT."
        )

    for filing in filings[:max_candidates]:
        time.sleep(_REQUEST_DELAY)
        url = _build_txt_url(cik, filing["accessionNumber"])
        response = requests.get(url, headers=_build_request_headers())
        response.raise_for_status()
        text = response.text

        if series_id is None:
            return url, filing, text
        m = re.search(r"<seriesId>\s*(S\d+)\s*</seriesId>", text)
        if m and m.group(1).upper() == series_id.upper():
            return url, filing, text

    raise LookupError(f"No N-PORT for series {series_id} in the {max_candidates} newest filings of CIK {cik}")

