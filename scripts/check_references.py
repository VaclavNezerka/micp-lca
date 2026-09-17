"""Verify every entry of paper/micp_lca_paper.bib against Crossref, DataCite, the DOI resolver and the publishers' pages.

Usage:  python scripts/check_references.py [KEY ...]

Writes paper/reference_check.md (one row per entry) and paper/reference_check.json. Entries with a DOI are compared with the
Crossref (or DataCite) record: title similarity, first author, year, volume and pages. Entries without a DOI (standards,
reports, databases, theses) are searched in Crossref by title and their URL is fetched. The verdicts are: VERIFIED (record
found, title and first author agree), RESOLVES (DOI resolves but the registry holds no comparable metadata), URL OK (document
reachable at the cited URL), STANDARD (CEN/ISO standard cited by its designation) and CHECK (needs a manual look; the
reason is given).
"""
from __future__ import annotations

import difflib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "paper" / "micp_lca_paper.bib"
OUT_MD = ROOT / "paper" / "reference_check.md"
OUT_JSON = ROOT / "paper" / "reference_check.json"
HDR = {"User-Agent": "micp-lca-refcheck/1.0 (mailto:vaclav.nezerka@cvut.cz)"}


def parse_bib(text: str) -> list[dict]:
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        typ, key = m.group(1).lower(), m.group(2)
        i, depth = m.end(), 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[m.end():i - 1]
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\"[^\"]*\"|[^,\n]+)", body):
            val = fm.group(2).strip()
            if val[:1] in "{\"":
                val = val[1:-1]
            fields[fm.group(1).lower()] = val.strip()
        entries.append({"type": typ, "key": key, **fields})
    return entries


def clean(s: str) -> str:
    s = re.sub(r"\\[\"'`^~=.vuHc]\s*", "", s)  # accent commands
    s = s.replace("\\i", "i").replace("\\j", "j")  # dotless i/j under accents
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = re.sub(r"<[^>]+>", "", s)  # MathML in Crossref titles
    s = re.sub(r"[{}$^_~]", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def first_author(a: str) -> str:
    a = a.split(" and ")[0]
    fam = a.split(",")[0] if "," in a else a.split()[-1]
    return clean(fam)


def year_of(e: dict) -> str:
    return re.sub(r"\D", "", e.get("year", ""))[:4]


def get(url: str, **kw):
    return requests.get(url, headers=HDR, timeout=40, **kw)


def crossref_doi(doi: str) -> dict | None:
    r = get(f"https://api.crossref.org/works/{doi}")
    return r.json()["message"] if r.status_code == 200 else None


def datacite_doi(doi: str) -> dict | None:
    r = get(f"https://api.datacite.org/dois/{doi}")
    return r.json()["data"]["attributes"] if r.status_code == 200 else None


def doi_resolves(doi: str) -> bool:
    r = get(f"https://doi.org/api/handles/{doi}")
    return r.status_code == 200 and r.json().get("responseCode") == 1


def crossref_search(query: str, rows: int = 3) -> list[dict]:
    r = get("https://api.crossref.org/works", params={"query.bibliographic": query, "rows": rows})
    return r.json()["message"]["items"] if r.status_code == 200 else []


def cr_year(item: dict) -> str:
    for k in ("published-print", "published-online", "issued", "created"):
        dp = item.get(k, {}).get("date-parts", [[None]])
        if dp and dp[0] and dp[0][0]:
            return str(dp[0][0])
    return ""


def cr_first_author(item: dict) -> str:
    au = item.get("author") or item.get("editor") or []
    return clean(au[0].get("family", "") or au[0].get("name", "")) if au else ""


def url_of(e: dict) -> str:
    for f in ("url", "howpublished", "note"):
        m = re.search(r"https?://[^\s}]+", e.get(f, ""))
        if m:
            return m.group(0)
    return ""


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def check(e: dict) -> dict:
    rec = {"key": e["key"], "type": e["type"], "year": year_of(e), "doi": e.get("doi", "").replace("https://doi.org/", ""), "url": url_of(e)}
    t_bib, a_bib = clean(e.get("title", "")), first_author(e.get("author", e.get("editor", "")))
    notes = []
    if rec["doi"]:
        item = crossref_doi(rec["doi"])
        if item:
            rec["registry"] = "Crossref"
            rec["found_title"] = (item.get("title") or [""])[0]
            rec["found_year"] = cr_year(item)
            rec["found_author"] = cr_first_author(item)
            rec["container"] = (item.get("container-title") or [""])[0]
            rec["title_sim"] = round(sim(t_bib, clean(rec["found_title"])), 2)
            au_ok = a_bib and (a_bib == rec["found_author"] or a_bib in rec["found_author"] or rec["found_author"] in a_bib)
            vol_ok = not (e.get("volume") and item.get("volume")) or e["volume"] == item["volume"]
            page_bib = e.get("pages", "").replace("--", "-").replace("\u2013", "-").split("-")[0]
            page_cr = (item.get("page", "") or item.get("article-number", "")).split("-")[0]
            page_ok = not (page_bib and page_cr) or page_bib == page_cr
            if not vol_ok:
                notes.append(f"volume {e.get('volume')} vs {item.get('volume')}")
            if not page_ok:
                notes.append(f"pages {e.get('pages')} vs {item.get('page') or item.get('article-number')}")
            if rec["year"] != rec["found_year"]:
                notes.append(f"year {rec['year']} vs {rec['found_year']} (print/online)")
            rec["verdict"] = "VERIFIED" if rec["title_sim"] >= 0.8 and au_ok and vol_ok and page_ok else "CHECK"
        else:
            dc = datacite_doi(rec["doi"])
            if dc:
                rec["registry"] = "DataCite"
                rec["found_title"] = (dc.get("titles") or [{}])[0].get("title", "")
                rec["found_year"] = str(dc.get("publicationYear", ""))
                rec["title_sim"] = round(sim(t_bib, clean(rec["found_title"])), 2)
                rec["verdict"] = "VERIFIED" if rec["title_sim"] >= 0.8 else "CHECK"
            elif doi_resolves(rec["doi"]):
                rec["registry"] = "doi.org"
                rec["verdict"] = "RESOLVES"
            else:
                rec["registry"] = "-"
                rec["verdict"] = "CHECK"
                notes.append("DOI does not resolve")
    else:
        if e["type"] in ("article", "inproceedings", "incollection", "book", "phdthesis", "unpublished") or e.get("journal"):
            best = None
            for it in crossref_search(f"{e.get('title', '')} {e.get('author', '')} {rec['year']}"):
                sc = sim(t_bib, clean((it.get("title") or [""])[0]))
                if best is None or sc > best[0]:
                    best = (sc, it)
            if best:
                sc, it = best
                rec["registry"] = "Crossref search"
                rec["found_title"] = (it.get("title") or [""])[0]
                rec["found_year"] = cr_year(it)
                rec["found_author"] = cr_first_author(it)
                rec["found_doi"] = it.get("DOI", "")
                rec["title_sim"] = round(sc, 2)
                if sc >= 0.85:
                    rec["verdict"] = "VERIFIED"
                    notes.append(f"DOI available: {rec['found_doi']}")
        if rec["url"]:
            try:
                r = get(rec["url"], allow_redirects=True, stream=True)
                rec["url_status"] = r.status_code
                if r.status_code < 400:
                    rec.setdefault("verdict", "URL OK")
                else:
                    notes.append(f"URL returns {r.status_code}")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"URL error {type(exc).__name__}")
        if "verdict" not in rec:
            rec["verdict"] = "CHECK"
            if clean(e.get("author", "")) in ("cen", "iso"):
                rec["verdict"] = "STANDARD"
                notes.append("published standard cited by its designation (no DOI; the catalogue pages block automated access)")
            elif e["type"] == "unpublished":
                notes.append("preprint of the authors (no identifier yet)")
            elif not rec["url"]:
                notes.append("no DOI or URL to verify automatically")
    rec["notes"] = "; ".join(notes)
    return rec


def main() -> None:
    entries = parse_bib(BIB.read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    results = []
    for e in entries:
        if only and e["key"] not in only:
            continue
        try:
            rec = check(e)
        except Exception as exc:  # noqa: BLE001
            rec = {"key": e["key"], "type": e["type"], "verdict": "ERROR", "notes": f"{type(exc).__name__}: {exc}"}
        results.append(rec)
        print(f"{rec['key']:32s} {rec['verdict']:10s} {rec.get('title_sim', '-')!s:5s} {rec.get('notes', '')}", flush=True)
        time.sleep(0.3)
    OUT_JSON.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    lines = ["# Verification of the bibliography", "",
             f"Generated by `scripts/check_references.py` from `paper/micp_lca_paper.bib` ({len(results)} entries). "
             "Every entry with a DOI was compared with its Crossref/DataCite record (title, first author, year, volume, pages); "
             "entries without a DOI were searched in Crossref and their URL was fetched.", "",
             "Summary: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())), "",
             "| Key | Type | Verdict | Registry | Title match | Found (title, container, year) | Notes |", "|---|---|---|---|---|---|---|"]
    for r in results:
        found = " — ".join(x for x in (r.get("found_title", "")[:80], r.get("container", ""), r.get("found_year", "")) if x)
        lines.append(f"| {r['key']} | {r.get('type', '')} | {r['verdict']} | {r.get('registry', '')} | {r.get('title_sim', '')} | {found} | {r.get('notes', '')} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("written", OUT_MD, counts)


if __name__ == "__main__":
    main()
