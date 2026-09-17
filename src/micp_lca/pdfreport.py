"""PDF report of one scenario: goal & scope, system, inventory, impact assessment, comparison, sensitivity,
uncertainty, cost, data quality, interpretation and references, with figures and a data-driven narrative.

The report is generated with ReportLab (platypus) and matplotlib; the text is assembled from the
results so that every number in the narrative is the one in the tables. References are numbered
in order of first citation and resolved from ``data/sources/sources.csv``.

Example::

    from micp_lca import load_data
    from micp_lca.pdfreport import build_report, ReportOptions
    data = load_data()
    build_report("GYP_WCFC_single_dose", data, "report.pdf", options=ReportOptions(author="V. Nežerka"))
"""
from __future__ import annotations

import datetime as _dt
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as _esc

import numpy as np
import pandas as pd

from . import __version__, figures
from .benchmarks import benchmark_impacts, compare_scenarios, compare_with_status_quo
from .cost import cost_summary
from .lcia import FU_LABELS, Results, run_scenario
from .loaders import DataBundle
from .parametric import SweepParameter, describe_sweep, effective_config, effective_protocol
from .sensitivity import oat_sensitivity

CORE = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP",
        "ADP-minerals&metals", "ADP-fossil", "WDP"]
ADDITIONAL = ["PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP"]
CATEGORY_NAMES = {"GWP-total": "Climate change, total", "GWP-fossil": "Climate change, fossil", "GWP-biogenic": "Climate change, biogenic",
                  "GWP-luluc": "Climate change, land use and land-use change", "ODP": "Ozone depletion", "AP": "Acidification",
                  "EP-freshwater": "Eutrophication, freshwater", "EP-marine": "Eutrophication, marine", "EP-terrestrial": "Eutrophication, terrestrial",
                  "POCP": "Photochemical ozone formation", "ADP-minerals&metals": "Resource use, minerals and metals",
                  "ADP-fossil": "Resource use, fossils", "WDP": "Water use", "PM": "Particulate matter", "IRP": "Ionising radiation",
                  "ETP-fw": "Ecotoxicity, freshwater", "HTP-c": "Human toxicity, cancer", "HTP-nc": "Human toxicity, non-cancer",
                  "SQP": "Land use (soil quality)"}
FU_SHORT = {"kg_product": "kg product", "m3_product": "m³ product", "m3_MPa": "m³·MPa", "kg_caco3_precipitated": "kg CaCO₃", "kg_solids": "kg solids"}
PATHWAY_NAMES = {"ureolytic": "ureolytic MICP", "organic_acid": "non-ureolytic MICP by oxidation of an organic calcium salt",
                 "fungal": "fungal biomineralisation", "eicp": "enzyme-induced carbonate precipitation (EICP)",
                 "denitrification": "denitrification-driven MICP", "photosynthetic": "photosynthetic (cyanobacterial) MICP",
                 "acetate_oxidation": "non-ureolytic MICP by acetate oxidation"}


@dataclass
class ReportOptions:
    title: str | None = None
    subtitle: str = ""
    author: str = ""
    organisation: str = ""
    functional_unit: str | None = None
    benchmarks: list[str] | None = None            # None = all benchmarks with impact data
    reference_benchmark: str = "AAC_block_ODB"
    comparison_scenarios: list[str] = field(default_factory=list)
    include_oat: bool = True
    oat_top: int = 12
    mc: Any = None                                 # micp_lca.uncertainty.MCResult
    sweep: pd.DataFrame | None = None
    sweep_parameter: SweepParameter | None = None
    notes: str = ""
    dpi: int = 170


# --------------------------------------------------------------------------------------------
# small helpers


def fmt(v: Any, sig: int = 3) -> str:
    """Compact number formatting for prose and tables."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    if isinstance(v, (float, np.floating)):
        a = abs(float(v))
        if a == 0:
            return "0"
        if a >= 1e5 or a < 1e-3:
            return f"{float(v):.{sig - 1}e}"
        if a >= 100:
            return f"{float(v):,.0f}"
        return f"{float(v):.{sig}g}"
    return str(v)


def _utxt(unit: str) -> str:
    """Unit for prose: dimensionless units are omitted."""
    return "" if unit in ("-", "–", "") else f" {unit}"


def _short_name(name: str, n: int = 60) -> str:
    """Shorten long dataset/material names at a word boundary."""
    base = str(name).split(" – ")[0].split(";")[0]
    if len(base) <= n:
        return base
    cut = base[:n].rsplit(" ", 1)[0]
    return cut + " …"


def pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.0f} %"


def _sub(s: str) -> str:
    """Chemical formulae with subscripts for ReportLab paragraphs."""
    out = s
    for k, v in (("CO2", "CO<sub>2</sub>"), ("NH4+", "NH<sub>4</sub><super>+</super>"), ("NH3", "NH<sub>3</sub>"), ("N2O", "N<sub>2</sub>O"),
                 ("CaCO3", "CaCO<sub>3</sub>"), ("CaCl2", "CaCl<sub>2</sub>"), ("H+", "H<super>+</super>"), ("m3", "m<super>3</super>"),
                 ("Ca(OH)2", "Ca(OH)<sub>2</sub>"), ("SO2", "SO<sub>2</sub>"), ("CO(NH2)2", "CO(NH<sub>2</sub>)<sub>2</sub>"),
                 ("HCO3-", "HCO<sub>3</sub><super>−</super>"), ("NO3-", "NO<sub>3</sub><super>−</super>"), ("N2", "N<sub>2</sub>"),
                 ("O2", "O<sub>2</sub>"), ("H2O", "H<sub>2</sub>O")):
        out = out.replace(k, v)
    return out


class Refs:
    """Numbered references in order of first citation, resolved from the sources table."""

    def __init__(self, sources: dict[str, dict[str, str]]):
        self.sources = sources
        self.order: list[str] = []

    def cite(self, *ids: str) -> str:
        nums = []
        for sid in ids:
            if sid not in self.sources:
                continue
            if sid not in self.order:
                self.order.append(sid)
            nums.append(self.order.index(sid) + 1)
        return f"[{', '.join(str(n) for n in nums)}]" if nums else ""

    def entries(self) -> list[tuple[int, str]]:
        out = []
        for i, sid in enumerate(self.order, 1):
            s = self.sources[sid]
            cit = str(s.get("citation", sid))
            url = str(s.get("doi_or_url", "") or "")
            if url and url != "nan":
                cit += f". {'https://doi.org/' + url if url[:3] == '10.' else url}"
            out.append((i, cit))
        return out


# --------------------------------------------------------------------------------------------
# ReportLab setup


def _fonts() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if "DejaVu" in pdfmetrics.getRegisteredFontNames():
        return "DejaVu"
    try:
        import matplotlib
        ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        pdfmetrics.registerFont(TTFont("DejaVu", str(ttf / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(ttf / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Italic", str(ttf / "DejaVuSans-Oblique.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-BoldItalic", str(ttf / "DejaVuSans-BoldOblique.ttf")))
        pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Italic", boldItalic="DejaVu-BoldItalic")
        return "DejaVu"
    except Exception:  # noqa: BLE001 - fall back to the built-in fonts
        return "Helvetica"


def _styles(font: str) -> dict[str, Any]:
    from reportlab.lib.enums import TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    bold = f"{font}-Bold" if font == "DejaVu" else "Helvetica-Bold"
    italic = f"{font}-Italic" if font == "DejaVu" else "Helvetica-Oblique"
    st = {
        "title": ParagraphStyle("title", fontName=bold, fontSize=20, leading=25, spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", fontName=font, fontSize=11.5, leading=15, textColor="#444444", spaceAfter=14),
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=13.5, leading=17, spaceBefore=12, spaceAfter=6, textColor="#1f3b5a"),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=4, textColor="#1f3b5a"),
        "body": ParagraphStyle("body", fontName=font, fontSize=8.8, leading=12.2, alignment=TA_JUSTIFY, spaceAfter=5),
        "small": ParagraphStyle("small", fontName=font, fontSize=7.4, leading=9.6, textColor="#333333", spaceAfter=4),
        "caption": ParagraphStyle("caption", fontName=italic, fontSize=7.6, leading=10, textColor="#333333", spaceBefore=2, spaceAfter=10),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=7.0, leading=8.6),
        "cellb": ParagraphStyle("cellb", fontName=bold, fontSize=7.0, leading=8.6),
        "ref": ParagraphStyle("ref", fontName=font, fontSize=7.6, leading=10, leftIndent=18, firstLineIndent=-18, spaceAfter=2),
        "bullet": ParagraphStyle("bullet", fontName=font, fontSize=8.8, leading=12.2, leftIndent=12, bulletIndent=2, spaceAfter=3, alignment=TA_JUSTIFY),
        "font": font, "bold": bold,
    }
    return st


# --------------------------------------------------------------------------------------------
# document assembly


class _Doc:
    """Collects flowables and provides paragraph/table/figure helpers."""

    def __init__(self, st: dict[str, Any], width: float):
        self.st = st
        self.width = width
        self.story: list[Any] = []
        self.n_fig = 0
        self.n_tab = 0

    # text -------------------------------------------------------------------------------------
    def p(self, text: str, style: str = "body") -> None:
        from reportlab.platypus import Paragraph
        self.story.append(Paragraph(text, self.st[style]))

    def h1(self, text: str) -> None:
        self.p(text, "h1")

    def h2(self, text: str) -> None:
        self.p(text, "h2")

    def bullets(self, items: list[str]) -> None:
        from reportlab.platypus import Paragraph
        for it in items:
            self.story.append(Paragraph(it, self.st["bullet"], bulletText="•"))

    def spacer(self, h: float = 6) -> None:
        from reportlab.platypus import Spacer
        self.story.append(Spacer(1, h))

    def page_break(self) -> None:
        from reportlab.platypus import PageBreak
        self.story.append(PageBreak())

    # tables -----------------------------------------------------------------------------------
    def table(self, rows: list[list[Any]], caption: str, col_widths: list[float] | None = None, align_right_from: int = 1,
              font_size: float = 7.0) -> None:
        from reportlab.lib import colors
        from reportlab.platypus import KeepTogether, Paragraph, Table, TableStyle
        self.n_tab += 1
        cell, cellb = self.st["cell"], self.st["cellb"]
        data = []
        for i, r in enumerate(rows):
            data.append([Paragraph(str(c), cellb if i == 0 else cell) for c in r])
        n_cols = max(len(r) for r in rows)
        if col_widths is None:
            col_widths = [self.width / n_cols] * n_cols
        t = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde6ef")), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#1f3b5a")),
                 ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#1f3b5a")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f8")]),
                 ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
                 ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        t.setStyle(TableStyle(style))
        cap = Paragraph(f"<b>Table {self.n_tab}.</b> {caption}", self.st["caption"])
        if len(rows) <= 14:
            self.story.append(KeepTogether([t, cap]))
        else:
            self.story.extend([t, cap])

    def df_table(self, df: pd.DataFrame, caption: str, index_label: str = "", fmt_cols: dict[str, int] | None = None,
                 col_widths: list[float] | None = None, sig: int = 3) -> None:
        cols = [index_label] + [str(c) for c in df.columns]
        rows = [cols]
        for idx, r in df.iterrows():
            rows.append([_esc(str(idx))] + [fmt(v, (fmt_cols or {}).get(str(c), sig)) if isinstance(v, (int, float, np.integer, np.floating)) else _esc(str(v)) for c, v in r.items()])
        if col_widths is None:
            first = min(0.34 * self.width, max(0.16 * self.width, 5.2 * max(len(str(i)) for i in df.index) + 10))
            rest = (self.width - first) / max(len(df.columns), 1)
            col_widths = [first] + [rest] * len(df.columns)
        self.table(rows, caption, col_widths)

    # figures ----------------------------------------------------------------------------------
    def figure(self, path: Path, caption: str, width: float | None = None) -> None:
        from reportlab.platypus import Image, KeepTogether, Paragraph
        from PIL import Image as PILImage
        self.n_fig += 1
        w = width or self.width
        with PILImage.open(path) as im:
            iw, ih = im.size
        h = w * ih / iw
        max_h = 0.62 * 842 * 0.72
        if h > max_h:
            w, h = w * max_h / h, max_h
        img = Image(str(path), width=w, height=h)
        img.hAlign = "CENTER"
        self.story.append(KeepTogether([img, Paragraph(f"<b>Figure {self.n_fig}.</b> {caption}", self.st["caption"])]))


# --------------------------------------------------------------------------------------------
# narrative helpers


def _group_shares(res: Results, category: str, modules: tuple[str, ...] = ("A1", "A2", "A3")) -> pd.Series:
    df = res.contrib[res.contrib["module"].isin(modules)].groupby("group")[category].sum()
    total = df.sum()
    return (df / total).sort_values(ascending=False) if total else df * 0


def _top_text(shares: pd.Series, n: int = 3) -> str:
    pos = shares[shares > 0.005].head(n)
    return ", ".join(f"{_esc(g)} ({100 * v:.0f} %)" for g, v in pos.items())


def _pathway_paragraph(meta: dict[str, Any], proto: dict[str, Any], refs: Refs) -> str:
    pw = meta.get("pathway", "")
    cs = meta.get("carbonate_source")
    txt = ""
    if pw == "ureolytic" or cs == "urea":
        txt = (f"In the ureolytic route the bacterial urease hydrolyses urea, CO(NH2)2 + 2 H2O → 2 NH4+ + CO3<super>2−</super>, and the carbonate "
               f"precipitates with the calcium of the calcium salt as CaCO3 {refs.cite('HOLECEK2024', 'KLIKOVA2025ESPR')}. The carbon of "
               f"synthetic urea is of fossil origin (natural-gas ammonia and CO2), so the share that is not fixed in CaCO3 is released as fossil "
               f"CO2 (0.733 kg CO2 per kg of urea when fully hydrolysed {refs.cite('IPCC2019')}); the nitrogen leaves the system as ammonium "
               f"in the effluent, as volatilised ammonia and as a small share of nitrous oxide {refs.cite('LEE2019', 'GOWTHAMAN2022')}.")
    elif pw in ("organic_acid", "acetate_oxidation") or cs == "organic":
        sub = meta.get("organic_substrate") or "lactate"
        txt = (f"In the non-ureolytic route heterotrophic bacteria oxidise the {sub} anion of the calcium salt; the metabolic CO2 raises the "
               f"carbonate concentration and pH in the micro-environment of the cells and CaCO3 precipitates without a nitrogen by-product "
               f"{refs.cite('KLIKOVA2025CCC', 'NEZERKA2026PRE')}. For calcium lactate one sixth of the substrate carbon is fixed in CaCO3 and "
               f"the rest is respired; the carbon is {'biogenic (fermentation of sugars)' if sub == 'lactate' else 'accounted according to the origin of the acetate'}.")
    elif pw == "fungal":
        txt = (f"The fungal route uses the mycelium of <i>Trichoderma reesei</i> as nucleation template and source of metabolic CO2; the calcium "
               f"salt supplies the cation {refs.cite('KLIKOVA2025JECE')}.")
    elif pw == "eicp" or cs == "urea" and "jack_bean" in str(proto.get("strain", "")):
        txt = (f"Enzyme-induced carbonate precipitation replaces the bacterial culture by free plant urease (jack-bean meal); the chemistry and "
               f"the nitrogen by-products are those of the ureolytic route {refs.cite('ALOTAIBI2022')}.")
    elif pw == "denitrification":
        txt = (f"Denitrifying bacteria oxidise acetate with nitrate as electron acceptor (5 CH<sub>3</sub>COO<super>−</super> + 8 NO3- → "
               f"10 HCO3- + 4 N2 + …); calcium nitrate and calcium acetate supply the reagents, the nitrogen leaves mainly as N2 with a small "
               f"N2O share, and residual nitrate is drained {refs.cite('VANPAASSEN2010', 'PORTER2021')}.")
    elif pw == "photosynthetic":
        txt = (f"Cyanobacteria consume dissolved bicarbonate and raise the pH photosynthetically; the light energy of the culture is modelled "
               f"as LED electricity {refs.cite('PORTER2021')}.")
    if float(meta.get("gypsum_fraction", 0) or 0) > 0:
        txt += (f" Waste gypsum ({100 * float(meta['gypsum_fraction']):.0f} % of the solids) promotes the formation of ettringite (AFt) with the "
                f"aluminate and portlandite of the fines, which is the main binder of the gypsum-promoted recipes; the microbially precipitated "
                f"CaCO3 is small in mass but modifies the microstructure {refs.cite('NEZERKA2026PRE')}.")
    return _sub(txt)


# --------------------------------------------------------------------------------------------
# the report


def build_report(scenario: str, data: DataBundle, out_path: Path | str, *, overrides: dict[str, Any] | None = None,
                 param_overrides: dict[str, float] | None = None, options: ReportOptions | None = None) -> Path:
    """Generate the PDF report for ``scenario`` (with optional overrides) and return its path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    opt = options or ReportOptions()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    font = _fonts()
    st = _styles(font)
    cfg = effective_config(scenario, data, overrides)
    proto = effective_protocol(cfg, data)
    fu = opt.functional_unit or cfg.get("functional_unit", "kg_product")
    res = run_scenario(scenario, data, functional_unit=fu, overrides=overrides, param_overrides=param_overrides)
    res_kg = res if fu == "kg_product" else run_scenario(scenario, data, functional_unit="kg_product", overrides=overrides, param_overrides=param_overrides)
    meta = res.meta
    refs = Refs(data.sources)
    fu_label = FU_LABELS.get(fu, fu)
    unit_gwp = data.category_unit("GWP-total")
    strains = {**data.strains, **(cfg.get("custom_strains") or {})}
    media = {**data.media, **(cfg.get("custom_media") or {})}
    materials = {**data.materials, **(cfg.get("custom_materials") or {})}
    chemicals = {**data.chemicals, **(cfg.get("custom_chemicals") or {})}
    strain = strains[proto["strain"]]
    material_id = cfg.get("material") or proto["material"]
    material = materials[material_id]
    scen_desc = cfg.get("description") or data.scenarios["scenarios"].get(scenario, {}).get("description", "")
    fu_short = FU_SHORT.get(fu, fu)

    def bname(b: str | None) -> str:
        if not b:
            return ""
        bd = data.scenarios["benchmarks"].get(b, {})
        return _esc(str(bd.get("name") or bd.get("description") or b).split(" (")[0][:70])
    title = opt.title or f"Life-cycle assessment of {scenario}"
    today = _dt.date.today().isoformat()

    page_w, page_h = A4
    margin = 18 * mm
    width = page_w - 2 * margin
    doc = _Doc(st, width)
    tmp = tempfile.TemporaryDirectory(prefix="micp_report_")
    tdir = Path(tmp.name)

    # ------------------------------------------------------------------------------ totals
    a13 = res.totals(("A1", "A2", "A3"))
    c14 = res.totals(("C1", "C2", "C3", "C4"))
    dmod = res.totals(("D",))
    gwp13, gwpc, gwpd = float(a13["GWP-total"]), float(c14["GWP-total"]), float(dmod["GWP-total"])
    shares_gwp = _group_shares(res, "GWP-total")
    bench_names = opt.benchmarks if opt.benchmarks is not None else [b for b in data.scenarios["benchmarks"] if b != "landfill_WCF_status_quo"]
    comp_results = [res_kg]
    for s in opt.comparison_scenarios:
        if s != scenario:
            try:
                comp_results.append(run_scenario(s, data, functional_unit="kg_product"))
            except Exception:  # noqa: BLE001
                pass
    comp_kg = compare_scenarios(comp_results, data, benchmarks=bench_names, category="GWP-total", functional_unit="kg_product")
    ref_b = opt.reference_benchmark if opt.reference_benchmark in data.scenarios["benchmarks"] else (bench_names[0] if bench_names else None)
    ref_kg = benchmark_impacts(ref_b, data, functional_unit="kg_product", include_eol=False) if ref_b else None
    ratio_gwp = res_kg.gwp() / float(ref_kg["GWP-total"]) if ref_kg is not None and float(ref_kg["GWP-total"]) else float("nan")

    # ------------------------------------------------------------------------------ title block
    doc.p(_esc(title), "title")
    sub = opt.subtitle or f"Ex-ante life-cycle assessment according to ISO 14040/14044 and EN 15804+A2 (EF 3.1), scenario <b>{_esc(scenario)}</b>"
    if scen_desc:
        sub += f"<br/>{_esc(str(scen_desc))}"
    who = " · ".join(x for x in (opt.author, opt.organisation) if x)
    sub += f"<br/>{_esc(who) + ' · ' if who else ''}{today} · generated with micp-lca {__version__}"
    doc.p(sub, "subtitle")

    # ------------------------------------------------------------------------------ 1 summary
    doc.h1("1. Summary")
    ref_txt = ""
    if ref_kg is not None and ratio_gwp == ratio_gwp:
        ref_txt = (f" Per kg of product the cradle-to-gate climate-change impact is {fmt(res_kg.gwp())} kg CO2 eq, i.e. "
                   f"{'%.0f %% %s' % (abs(100 * (ratio_gwp - 1)), 'lower than' if ratio_gwp < 1 else 'higher than')} the reference product "
                   f"{bname(ref_b)} ({fmt(float(ref_kg['GWP-total']))} kg CO2 eq/kg, A1–A3).")
    doc.p(_sub(
        f"This report documents an ex-ante, attributional life-cycle assessment of the biocementation scenario <b>{_esc(scenario)}</b>: "
        f"{PATHWAY_NAMES.get(meta.get('pathway', ''), meta.get('pathway', ''))} of {_esc(_short_name(material.get('name', material_id)))} "
        f"with <i>{_esc(strain.get('name', proto['strain']))}</i>. The functional unit is <b>{fu_label}</b>. "
        f"The cradle-to-gate (modules A1–A3) climate-change impact is <b>{fmt(gwp13)} {unit_gwp}</b> per functional unit; the end of life "
        f"(C1–C4) adds {fmt(gwpc)} and module D contributes {fmt(gwpd)} {unit_gwp}. The largest contributors to GWP-total are "
        f"{_top_text(shares_gwp)}.{ref_txt} Acidification amounts to {fmt(float(a13['AP']))} mol H+ eq, terrestrial eutrophication to "
        f"{fmt(float(a13['EP-terrestrial']))} mol N eq and water use to {fmt(float(a13['WDP']))} m3 world eq deprived per functional unit "
        f"(A1–A3). The climate-change indicator is covered by native background data for {pct(res.coverage_native.get('GWP-total', float('nan')))} of the "
        f"inventory (by mass-weighted GWP); acidification for {pct(res.coverage_native.get('AP', float('nan')))} natively and "
        f"{pct(res.coverage.get('AP', float('nan')))} including scaled proxy profiles."))

    # ------------------------------------------------------------------------------ 2 goal and scope
    doc.h1("2. Goal and scope")
    doc.p(_sub(
        f"The goal is to quantify the potential environmental impacts of producing biocemented blocks from waste concrete fines "
        f"or sub-sieve demolition residues by the route described in Section 3, to identify the dominant contributions and to compare the product with conventional "
        f"masonry units. The study follows ISO 14040/14044 {refs.cite('ISO14040')} and the modular structure, indicator set and "
        f"biogenic-carbon conventions of EN 15804:2012+A2:2019 {refs.cite('EN15804')}; impacts are characterised with the Environmental "
        f"Footprint 3.1 method {refs.cite('EF31', 'PEF2021')}. Because the technology is at laboratory scale, the assessment is <i>ex-ante</i>: "
        f"the laboratory protocol is reproduced one-to-one and its energy and auxiliary demands are translated to an industrial process "
        f"with the scale-up framework of Piccinno et al. {refs.cite('PICCINNO2016')} and the recommendations for prospective LCA "
        f"{refs.cite('TSOY2020', 'VDGIESEN2020', 'THONEMANN2020')}."))
    doc.bullets([_sub(x) for x in [
        f"<b>Functional unit:</b> {fu_label}. Conversions use a product bulk density of {fmt(res.inventory.bulk_density_kg_m3)} kg/m3"
        + (f" and a compressive strength of {fmt(res.inventory.fc_MPa)} MPa" if res.inventory.fc_MPa else "") + ".",
        "<b>System boundary:</b> A1 (processing of the waste fines and gypsum after the end-of-waste point, production of chemicals, media "
        "components and water), A2 (transport of inputs), A3 (cultivation of the microbial suspension, casting, dosing, curing, drying, effluent "
        "treatment, direct process emissions and carbonation uptake), C1–C4 (demolition, transport, recycling or inert landfill) and, "
        "optionally, D (credits for recovered nitrogen). The use stage (B) is not modelled: the product is inert in use.",
        f"<b>Secondary materials:</b> the waste fines and waste gypsum enter burden-free (polluter-pays / cut-off approach {refs.cite('EN15804')}); "
        "only their processing and transport are included.",
        f"<b>Biogenic carbon:</b> {'the EF 3.1 convention (biogenic CO2 uptakes and emissions characterised with zero)' if cfg.get('carbon_accounting', 'EF31') == 'EF31' else 'the EN 15804+A2 −1/+1 convention (uptake of biogenic carbon in the product as −1, release at the end of life as +1)'}; "
        "the carbon of synthetic urea is fossil and the CO2 taken up by carbonation of the portlandite in the fines is accounted for as an uptake "
        f"following EN 16757 {refs.cite('EN16757')}.",
        f"<b>Geography and time:</b> production in the Czech Republic ({_esc(cfg.get('electricity', 'electricity_CZ_lv'))} electricity, "
        f"{refs.cite('EMBER2024')}); background data of 2020–2024 {refs.cite('OBD2024II', 'AGRIBALYSE4')}; laboratory data of 2023–2026.",
        "<b>Cut-off:</b> capital goods, laboratory consumables and packaging are excluded; the laboratory equipment energy is replaced by the "
        "industrial process model (Section 3.2).",
        f"<b>Data quality:</b> every background factor carries a source, pedigree scores {refs.cite('WEIDEMA1996', 'CIROTH2016')} and, where "
        "available, a literature range; coverage of each indicator by native versus proxy factors is reported (Section 9).",
    ]])

    # ------------------------------------------------------------------------------ 3 system description
    doc.h1("3. System description")
    doc.h2("3.1 Composition and protocol")
    doc.p(_pathway_paragraph(meta, proto, refs))
    cult = strain.get("cultivation") or {}
    variant = cfg.get("cultivation_variant") or proto.get("cultivation_variant")
    if variant and variant in (strain.get("alternative_cultivation_media") or {}):
        cult = {**cult, **strain["alternative_cultivation_media"][variant]}
    bs = proto.get("biocementation_solution") or {}
    dosing = bs.get("dosing") or {}
    comp_rows = [["Item", "Value"]]

    def med_desc(mid: str | None) -> str:
        if not mid or mid not in media:
            return _esc(str(mid))
        comps = media[mid].get("components") or {}
        return _esc(f"{media[mid].get('name', mid)}: " + ", ".join(f"{(chemicals.get(k) or {}).get('name', k).split(' (')[0]} {v} g/L" for k, v in comps.items()))

    comp_rows += [
        ["Waste material", _esc(f"{material.get('name', material_id)}; portlandite {material.get('portlandite_wt', 0)} wt%, CaCO3 {material.get('caco3_wt', 'n/a')} wt%; transport {material.get('transport_km', 70)} km")],
        ["Dry solids per specimen", f"{fmt(float(proto.get('solids_g', 0)))} g, of which waste gypsum {100 * float(proto.get('gypsum_fraction', 0) or 0):.1f} %"],
        ["Organism / catalyst", _esc(f"{strain.get('name', proto['strain'])} ({strain.get('pathway', '')})")],
        ["Cultivation", _esc(f"{cult.get('temperature_C', 'n/a')} °C, {cult.get('duration_h', 'n/a')} h, harvest at OD600 {cfg.get('harvest_od600_override') or cult.get('harvest_od600', 'n/a')}, {cult.get('harvest', 'no harvest')}") if not cfg.get("abiotic") else "none (abiotic control)"],
        ["Cultivation medium", med_desc(cult.get("medium")) if not cfg.get("abiotic") else "none (abiotic control)"],
        ["Suspension per specimen", _esc(f"{(proto.get('suspension') or {}).get('volume_mL', 0)} mL at OD600 {(proto.get('suspension') or {}).get('od600', 'n/a')}")],
        ["Casting", _esc(f"saline {proto.get('saline_mL', 0)} mL; HCl {(proto.get('hcl') or {}).get('molarity', 0)} M × {(proto.get('hcl') or {}).get('volume_mL', 0)} mL; mixing {(proto.get('mixing') or {}).get('vibration_s', 'n/a')} s")],
        ["Biocementation solution", med_desc(bs.get("base_medium"))],
        ["Reagents (supplements)", _esc(", ".join(f"{(chemicals.get(k) or {}).get('name', k).split(' (')[0]} {fmt(float(v))} g/L" for k, v in (bs.get("supplements") or {}).items()) or "none")],
        ["Dosing", _esc(f"{dosing.get('mode', 'repeated')}: {meta.get('n_doses')} dose(s) × {bs.get('dose_mL', 0)} mL"
                        + (f", every {dosing.get('interval_h')} h over {dosing.get('duration_d', (proto.get('incubation') or {}).get('duration_d'))} d" if dosing.get("mode", "repeated") == "repeated" else ""))],
        ["Biocementation (curing)", f"{fmt(meta.get('T_incubation_C'))} °C for {fmt(meta.get('incubation_d'))} d"],
        ["Drying / conditioning", f"{fmt(meta.get('drying_d'))} d at {(proto.get('drying') or {}).get('temperature_C', 'ambient')} °C"],
        ["Specimen / product", _esc(f"{(proto.get('specimen') or {}).get('shape', 'n/a')} {(proto.get('specimen') or {}).get('diameter_mm', '')}×{(proto.get('specimen') or {}).get('height_mm', '')} mm; "
                                    f"bulk density {fmt(res.inventory.bulk_density_kg_m3)} kg/m3; fc {fmt(res.inventory.fc_MPa)} MPa; product mass {fmt(meta.get('product_kg_per_kg_solids'))} kg per kg solids")],
        ["Protocol source", _esc(str(proto.get("source_id", ""))) + " " + refs.cite(str(proto.get("source_id", "")))],
    ]
    doc.table(comp_rows, f"Composition and laboratory protocol of scenario {_esc(scenario)}.", [0.28 * width, 0.72 * width])

    doc.h2("3.2 Technology and system settings")
    from .inventory import Params
    scale = cfg.get("scale", "industrial")
    P = Params(data.scaleup, scale, {**(cfg.get("scaleup_overrides") or {}), **(param_overrides or {})})
    elec = data.background.get(cfg.get("electricity", "electricity_CZ_lv"))
    tech_rows = [["Setting", "Value"],
                 ["Energy model", "industrial process model (scale-up)" if scale == "industrial" else "laboratory equipment energy (as performed in the lab)"],
                 ["Electricity", _esc(f"{elec.name if elec else cfg.get('electricity')}, {fmt(elec.gwp_any) if elec else 'n/a'} kg CO2 eq/kWh")],
                 ["Curing heat", _esc(f"{_short_name(data.background[P.text('industrial.curing_chamber.heat_carrier', 'heat_natural_gas')].name, 45) if P.text('industrial.curing_chamber.heat_carrier', 'heat_natural_gas') in data.background else P.text('industrial.curing_chamber.heat_carrier', 'heat_natural_gas')}; chamber U = {fmt(P.get('industrial.curing_chamber.U_W_m2K'))} W/(m²K), "
                                      f"ambient {fmt(P.get('industrial.curing_chamber.ambient_C'))} °C, {fmt(P.get('industrial.curing_chamber.chamber_m3_per_t_product'))} m³ chamber per t product") if scale == "industrial" else "incubator"],
                 ["Medium sterilisation", f"autoclave-type heating to {fmt(P.get('industrial.medium_sterilisation.hold_C', 121))} °C with {pct(P.get('industrial.medium_sterilisation.heat_recovery'))} heat recovery" if scale == "industrial" else "laboratory autoclave"],
                 ["Fermentation", f"{fmt(P.get('industrial.fermentation.power_kW_per_m3'))} kW/m³ agitation and aeration; temperature control {fmt(P.get('industrial.fermentation.temperature_control_kWh_per_m3_day'))} kWh/(m³·d)" if scale == "industrial" else "shaking incubator"],
                 ["Effluent", f"{pct(P.get('industrial.effluent.fraction_drained'))} of the liquids drained; nitrogen treatment: {_esc(cfg.get('effluent_treatment', 'none'))}; module D credits: {'yes' if cfg.get('module_d') else 'no'}"],
                 ["Nitrogen fate parameters", f"urea hydrolysed {pct(P.get('industrial.nitrogen_fate.urea_hydrolysed_fraction'))}; NH3 volatilised {pct(P.get('industrial.nitrogen_fate.nh3_volatilised_fraction_of_retained_N'))} of the retained N; N2O {100 * P.get('industrial.nitrogen_fate.n2o_fraction_of_N'):.2f} % of N"],
                 ["Carbonation", f"{pct(float(cfg.get('carbonation_uptake_fraction', 0)))} of the portlandite carbonated within the life cycle (EN 16757 convention)"],
                 ["End of life", f"{_esc(cfg.get('eol', 'landfill'))} after demolition (2 kWh/t) and 50 km transport"],
                 ["Impact assessment", f"EF 3.1; biogenic carbon: {_esc(cfg.get('carbon_accounting', 'EF31'))}; site-specific (CZ) factors for AP/EP: {'yes' if cfg.get('site_specific_cf') else 'no'}"],
                 ["Transport distances", f"chemicals {fmt(float(cfg.get('transport_chemicals_km', 200)))} km, gypsum {fmt(float(cfg.get('transport_gypsum_km', 100)))} km, feathers {fmt(float(cfg.get('transport_feathers_km', 80)))} km (lorry)"]]
    doc.table([[_sub(str(c)) for c in r] for r in tech_rows], "Technology and system settings of the assessed scenario.", [0.28 * width, 0.72 * width])

    # ------------------------------------------------------------------------------ 4 inventory
    doc.h1("4. Life-cycle inventory")
    inv = res.inventory
    ff = res.fu_factor
    S_txt = fmt(1.0 / max(meta.get("product_kg_per_kg_solids", 1.0), 1e-12))
    doc.p(_sub(
        f"All quantities were first computed per laboratory specimen ({fmt(1000 * meta.get('solids_kg_per_specimen', 0))} g of dry solids) exactly as "
        f"described in the protocol, then normalised per kg of dry input solids and finally converted to the functional unit "
        f"(1 {fu_label} corresponds to {fmt(ff)} kg of dry solids). The liquid-to-solid ratio of the process is "
        f"{fmt(meta.get('liquid_to_solid_L_per_kg'))} L per kg of solids: {fmt(meta.get('V_biocementation_solution_L', 0) / max(meta.get('solids_kg_per_specimen', 1), 1e-12))} L/kg of "
        f"biocementation solution in {meta.get('n_doses')} dose(s), {fmt(meta.get('V_suspension_L', 0) / max(meta.get('solids_kg_per_specimen', 1), 1e-12))} L/kg of bacterial "
        f"suspension (from {fmt(meta.get('V_culture_L', 0) / max(meta.get('solids_kg_per_specimen', 1), 1e-12))} L/kg of culture) and "
        f"{fmt(meta.get('V_saline_L', 0) / max(meta.get('solids_kg_per_specimen', 1), 1e-12))} L/kg of saline. One kg of dry product contains {S_txt} kg of input solids."))
    # reagent / carbon / nitrogen balance
    bal_rows = [["Quantity", "per kg of dry solids", f"per {fu_label}"]]
    keys = [("urea_kg_per_kg_solids", "Urea, kg"), ("ca_mol_per_kg_solids", "Calcium in reagents, mol"), ("urea_to_ca_molar_ratio", "Urea : Ca molar ratio, mol/mol"),
            ("caco3_theoretical_kg_per_kg_solids", "CaCO3, theoretical (limiting reagent), kg"), ("caco3_precipitated_kg_per_kg_solids", "CaCO3, precipitated (model / measured cap), kg"),
            ("precipitation_efficiency", "Precipitation efficiency, –"), ("co2_fossil_direct_kg_per_kg_solids", "Direct fossil CO2 released, kg"),
            ("co2_biogenic_direct_kg_per_kg_solids", "Direct biogenic CO2 released, kg"), ("c_stored_fossil_as_co2_kg_per_kg_solids", "Fossil carbon stored in CaCO3 (as CO2), kg"),
            ("c_stored_biogenic_as_co2_kg_per_kg_solids", "Biogenic carbon stored in CaCO3 (as CO2), kg"), ("carbonation_uptake_kg_per_kg_solids", "CO2 uptake by carbonation of portlandite, kg"),
            ("n_hydrolysed_kg_per_kg_solids", "Nitrogen released by urea hydrolysis, kg"), ("nitrate_n_denitrified_kg_per_kg_solids", "Nitrate-N denitrified, kg"),
            ("effluent_L_per_kg_solids", "Effluent drained, L"), ("product_kg_per_kg_solids", "Product mass, kg")]
    for k, lab in keys:
        v = meta.get(k)
        if v is None or (isinstance(v, float) and (math.isnan(v) or (v == 0 and k not in ("caco3_precipitated_kg_per_kg_solids",)))):
            continue
        per_fu = v * ff if k not in ("urea_to_ca_molar_ratio", "precipitation_efficiency") else v
        bal_rows.append([_sub(lab), fmt(v), fmt(per_fu)])
    doc.table(bal_rows, "Reagent, carbon and nitrogen balance of the biocementation step.", [0.5 * width, 0.25 * width, 0.25 * width])
    nf = meta.get("nitrogen_fate_kg_per_kg_solids") or {}
    if sum(nf.values()) > 0:
        nfig = figures.nitrogen_fate({k: v * ff for k, v in nf.items()}, tdir / "nfate.png")
        doc.figure(nfig, "Fate of the nitrogen released by urea hydrolysis (shares of the released N): ammonium drained with the effluent, "
                         "ammonia volatilised from the retained liquid, nitrous oxide, nitrogen recovered by the effluent treatment and nitrogen retained in the product.", width=0.7 * width)
    # inventory table of the main flows
    ct = res.contrib.copy()
    ct["amount_fu"] = ct["amount"] * ff
    bg = ct[ct["kind"] == "background"].groupby(["module", "group", "key", "unit"], as_index=False).agg(amount_fu=("amount_fu", "sum"), gwp=("GWP-total", "sum"))
    bg["share"] = bg["gwp"] / (gwp13 + gwpc + gwpd) if (gwp13 + gwpc + gwpd) else float("nan")
    bg = bg.reindex(bg["gwp"].abs().sort_values(ascending=False).index).head(18)
    rows = [["Module", "Process group", "Dataset", "Amount", "Unit", "GWP-total", "Share"]]
    for _, r in bg.iterrows():
        rows.append([r["module"], _esc(r["group"]), _esc(_short_name(data.background[r["key"]].name, 58) if r["key"] in data.background else r["key"]), fmt(r["amount_fu"]), r["unit"], fmt(r["gwp"]), pct(r["share"])])
    doc.table(rows, f"Main background flows of the inventory per {fu_label}, ranked by their contribution to GWP-total (A1–A3 + C + D).",
              [0.09 * width, 0.2 * width, 0.35 * width, 0.1 * width, 0.06 * width, 0.11 * width, 0.09 * width])
    el = ct[ct["kind"] == "elementary"].groupby(["group", "key", "compartment", "unit"], as_index=False).agg(amount_fu=("amount_fu", "sum"), gwp=("GWP-total", "sum"), ap=("AP", "sum"), ept=("EP-terrestrial", "sum"))
    el = el[el["amount_fu"] != 0]
    if len(el):
        rows = [["Elementary flow", "Process group", "Compartment", "Amount", "Unit", "GWP-total", "AP", "EP-terrestrial"]]
        for _, r in el.iterrows():
            rows.append([_esc(r["key"]), _esc(r["group"]), r["compartment"], fmt(r["amount_fu"]), r["unit"], fmt(r["gwp"]), fmt(r["ap"]), fmt(r["ept"])])
        doc.table(rows, f"Direct (elementary) flows of the process per {fu_label} and their characterised impacts (EF 3.1); a negative CO2 flow is the carbonation uptake.",
                  [0.19 * width, 0.15 * width, 0.14 * width, 0.1 * width, 0.06 * width, 0.12 * width, 0.1 * width, 0.14 * width])

    # ------------------------------------------------------------------------------ 5 impact assessment
    doc.h1("5. Life-cycle impact assessment")
    ind_rows = [["Indicator", "Unit", "A1–A3", "C1–C4", "D", "Total", "Coverage native / incl. proxies"]]
    for c in CORE + ADDITIONAL:
        if c not in res.categories:
            continue
        ind_rows.append([_esc(f"{CATEGORY_NAMES.get(c, c)} ({c})"), _sub(_esc(data.category_unit(c))), fmt(float(a13[c])), fmt(float(c14[c])), fmt(float(dmod[c])),
                         fmt(float(a13[c] + c14[c] + dmod[c])), f"{pct(res.coverage_native.get(c, float('nan')))} / {pct(res.coverage.get(c, float('nan')))}"])
    doc.table(ind_rows, f"EF 3.1 impact indicators per {fu_label} (EN 15804+A2 core indicators first; the additional indicators are not declared by all "
                        "generic background datasets and should be interpreted with care).",
              [0.3 * width, 0.14 * width, 0.1 * width, 0.1 * width, 0.08 * width, 0.1 * width, 0.18 * width])
    f1 = figures.contribution_by_group(res, "GWP-total", unit_gwp, tdir / "contrib_gwp.png")
    doc.figure(f1, f"Contribution of the process groups to the climate-change indicator (GWP-total) per {fu_label}, stacked by life-cycle module. "
                   "Negative bars are uptakes or credits.")
    shares_ap = _group_shares(res, "AP")
    shares_ep = _group_shares(res, "EP-terrestrial")
    shares_wdp = _group_shares(res, "WDP")
    by_mod = res.by_module()["GWP-total"]
    tot_all = float(by_mod.sum()) or float("nan")
    doc.p(_sub(
        f"Cradle-to-gate, the climate-change result is dominated by {_top_text(shares_gwp)}. Module A1 (materials, chemicals and media) accounts for "
        f"{pct(float(by_mod.get('A1', 0)) / tot_all)}, A2 (transport) for {pct(float(by_mod.get('A2', 0)) / tot_all)} and A3 (manufacturing, including "
        f"direct emissions and carbonation) for {pct(float(by_mod.get('A3', 0)) / tot_all)} of the total including the end of life. "
        f"Acidification is driven by {_top_text(shares_ap)}; terrestrial eutrophication by {_top_text(shares_ep)}; water use by {_top_text(shares_wdp)}."
        + (f" The direct process emissions (fossil CO2 from urea hydrolysis, ammonia and nitrous oxide) are responsible for "
           f"{pct(float(shares_gwp.get('Direct process emissions', 0)))} of GWP-total and {pct(float(shares_ap.get('Direct process emissions', 0)))} of the acidification."
           if shares_gwp.get("Direct process emissions", 0) > 0.02 or shares_ap.get("Direct process emissions", 0) > 0.05 else "")))
    f2 = figures.indicator_profile(res, [c for c in CORE if c in res.categories], tdir / "profile.png")
    doc.figure(f2, "Share of the process groups in every EN 15804+A2 core indicator (A1–A3). Indicators that are dominated by a single group "
                   "point to the input whose data quality matters most for that indicator.")
    f3 = figures.module_split(res, [c for c in CORE if c in res.categories], tdir / "modules.png")
    doc.figure(f3, "Split of each indicator between the life-cycle modules A1, A2, A3, C1–C4 and D.")
    # carbon waterfall
    comp = {}
    bgA1 = float(ct[(ct["kind"] == "background") & (ct["module"] == "A1")]["GWP-total"].sum())
    bgA2 = float(ct[(ct["kind"] == "background") & (ct["module"] == "A2")]["GWP-total"].sum())
    bgA3 = float(ct[(ct["kind"] == "background") & (ct["module"] == "A3")]["GWP-total"].sum())
    dfoss = float(ct[(ct["kind"] == "elementary") & (ct["group"] == "Direct process emissions") & (ct["key"] == "carbon dioxide (fossil)")]["GWP-total"].sum())
    dbio = float(ct[(ct["kind"] == "elementary") & (ct["key"] == "carbon dioxide (biogenic)")]["GWP-total"].sum())
    dother = float(ct[(ct["kind"] == "elementary") & (ct["group"] == "Direct process emissions") & (~ct["key"].isin(["carbon dioxide (fossil)", "carbon dioxide (biogenic)"]))]["GWP-total"].sum())
    dup = float(ct[ct["group"] == "Carbonation uptake"]["GWP-total"].sum())
    eol = float(ct[ct["module"].isin(["C1", "C2", "C3", "C4"])]["GWP-total"].sum())
    dcred = float(ct[ct["module"] == "D"]["GWP-total"].sum())
    for k, v in (("A1 materials,\nchemicals, media", bgA1), ("A2 transport", bgA2), ("A3 energy &\nauxiliaries", bgA3), ("direct fossil CO$_2$", dfoss),
                 ("direct biogenic CO$_2$", dbio), ("N$_2$O & other direct", dother), ("carbonation uptake", dup), ("end of life C1–C4", eol), ("module D", dcred)):
        if abs(v) > 1e-9:
            comp[k] = v
    f4 = figures.carbon_waterfall(comp, unit_gwp, fu_short, tdir / "waterfall.png")
    doc.figure(f4, f"Climate-change balance per {fu_label}: background contributions by module, direct process emissions, carbonation uptake, "
                   "end of life and credits, adding up to the net life-cycle result.")

    # ------------------------------------------------------------------------------ 6 comparison
    doc.h1("6. Comparison with conventional products")
    f5 = figures.benchmark_comparison(comp_kg, "GWP-total", unit_gwp, "kg of product", tdir / "benchmarks.png", highlight=scenario)
    doc.figure(f5, "Climate-change impact per kg of product of the assessed scenario (red), other scenarios (blue) and benchmark products (grey): "
                   f"A1–A3 (solid) and C1–C4 (hatched). Benchmark data: ÖKOBAUDAT {refs.cite('OBD2024II')}, EPD {refs.cite('ENVIRONDEC3048')} and "
                   f"Nežerka et al. {refs.cite('NEZERKA2023LCA')}.")
    rows = [["Product", "Type", "GWP A1–A3", "GWP A1–A3 + C", "fc [MPa]", "Density [kg/m3]", "GWP per m3 (A1–A3)"]]
    for name, r in comp_kg.iterrows():
        dens = r.get("bulk_density_kg_m3")
        per_m3 = float(r[f"GWP-total A1-A3"]) * float(dens) if dens == dens and dens else float("nan")
        rows.append([_esc(str(name)), r["type"], fmt(float(r["GWP-total A1-A3"])), fmt(float(r["GWP-total A1-A3+C"])), fmt(r.get("fc_MPa")), fmt(dens), fmt(per_m3)])
    doc.table([[_sub(c) for c in r] for r in rows], "Climate-change impact of the assessed scenario and the benchmark products per kg of product and per m3.",
              [0.28 * width, 0.11 * width, 0.12 * width, 0.14 * width, 0.09 * width, 0.12 * width, 0.14 * width])
    tab_comp = doc.n_tab
    if ref_kg is not None:
        ratios_all = pd.Series({c: float(res_kg.totals(("A1", "A2", "A3"))[c]) / float(ref_kg[c]) for c in CORE if c in res.categories and ref_kg.get(c, float("nan")) == ref_kg.get(c, float("nan")) and float(ref_kg[c]) != 0})
        ratios = ratios_all[(ratios_all > 1e-4) & (ratios_all < 1e4)]
        omitted = [c for c in ratios_all.index if c not in ratios.index]
        f6 = figures.ratio_to_reference(ratios, _esc(ref_b), tdir / "ratio.png")
        doc.figure(f6, f"Ratio of the indicators of the assessed scenario to those of the reference product {_esc(ref_b)} (A1–A3, per kg of product; "
                       "values below 1 are favourable). Indicators with a negative or zero reference value" + (f", and {_esc(', '.join(omitted))} (reference value close to zero, ratio outside 10<super>−4</super>–10<super>4</super>)" if omitted else "") + " are omitted.")
        better = [c for c, v in ratios.items() if v < 1]
        worse = [c for c, v in ratios.items() if v >= 1]
        doc.p(_sub(f"Relative to {bname(ref_b)}, the scenario performs better in "
                   f"{len(better)} of {len(ratios)} core indicators ({_esc(', '.join(better)) or 'none'}) and worse in {len(worse)} "
                   f"({_esc(', '.join(worse)) or 'none'}). "
                   + ("The mass-based comparison favours the light benchmark products; per m3 the picture changes with the bulk density "
                      f"({fmt(res.inventory.bulk_density_kg_m3)} kg/m3 for the biocemented product), and per unit of strength it depends on the "
                      "compressive strength, which for the biocemented products is limited to non-load-bearing applications." if fu == "kg_product" else "")))
    try:
        sq = compare_with_status_quo(res_kg, data, ref_b or "AAC_block_ODB", "GWP-total")
        doc.p(_sub(f"<b>System expansion.</b> A biocemented block absorbs waste fines that would otherwise be landfilled. Comparing the block "
                   f"({fmt(sq['biocemented_block'])} kg CO2 eq/kg, A1–A3 + C1–C4) with the basket \"{_esc(ref_b)} + landfilling of the same mass of fines\" "
                   f"({fmt(sq['status_quo_basket'])} kg CO2 eq/kg) gives a difference of {fmt(sq['difference_bio_minus_status_quo'])} kg CO2 eq per kg of product "
                   f"({'in favour of' if sq['difference_bio_minus_status_quo'] < 0 else 'against'} the biocemented block)."))
    except Exception:  # noqa: BLE001
        pass

    # ------------------------------------------------------------------------------ 7 parametric & sensitivity
    doc.h1("7. Parametric analysis and sensitivity")
    sec = 0
    if opt.sweep is not None and opt.sweep_parameter is not None and len(opt.sweep):
        sec += 1
        sp = opt.sweep_parameter
        sw = opt.sweep
        panels = [("GWP-total", f"GWP-total [{unit_gwp}]"), ("AP", f"AP [{data.category_unit('AP')}]"), ("EP-terrestrial", f"EP-terrestrial [{data.category_unit('EP-terrestrial')}]")]
        if "cost_bulk_EUR" in sw:
            panels.append(("cost_bulk_EUR", "cost, bulk grade [EUR]"))
        else:
            panels.append(("WDP", f"WDP [{data.category_unit('WDP')}]"))
        f7 = figures.sweep_panels(sw, f"{sp.label}" + (f" [{sp.unit}]" if _utxt(sp.unit) else ""), sp.value, panels, tdir / "sweep.png", fu_short)
        doc.h2(f"7.{sec} Parametric analysis: {_esc(sp.label)}")
        doc.figure(f7, f"Response of the main indicators (and the indicative cost) per {fu_label} to the variation of <i>{_esc(sp.label)}</i> "
                       f"between {fmt(sp.lo)} and {fmt(sp.hi)}{_esc(_utxt(sp.unit))}; the dashed line marks the value of the assessed scenario ({fmt(sp.value)}).")
        d = describe_sweep(sw, "GWP-total")
        if d:
            txt = (f"Over the investigated range GWP-total {d['monotonic']} from {fmt(d['y_at_min_x'])} to {fmt(d['y_at_max_x'])} {unit_gwp} "
                   f"(span {100 * d['relative_span']:.0f} % of the value at the lower limit); the minimum ({fmt(d['y_min'])}) is reached at "
                   f"{fmt(d['x_of_y_min'])}{_esc(_utxt(sp.unit))}. ")
            if d["r2_linear"] == d["r2_linear"]:
                txt += (f"A straight line explains {100 * d['r2_linear']:.0f} % of the variance (slope {fmt(d['slope'])} {unit_gwp} per unit of the parameter), "
                        + ("so the response is essentially linear in this range. " if d["r2_linear"] > 0.98 else "so the response is clearly non-linear, which is typical for parameters that change the number of doses or the reagent stoichiometry. "))
            da = describe_sweep(sw, "AP")
            if da:
                txt += f"Acidification {da['monotonic']} over the same range ({fmt(da['y_at_min_x'])} → {fmt(da['y_at_max_x'])} mol H+ eq). "
            if "cost_bulk_EUR" in sw:
                dc = describe_sweep(sw, "cost_bulk_EUR")
                if dc:
                    txt += f"The indicative production cost {dc['monotonic']} from {fmt(dc['y_at_min_x'])} to {fmt(dc['y_at_max_x'])} EUR per {fu_label}."
            doc.p(_sub(txt))
        cols = [c for c in ["value", "GWP-total", "GWP-fossil", "AP", "EP-terrestrial", "WDP", "cost_bulk_EUR", "caco3_kg_per_kg_solids", "n_doses"] if c in sw]
        show = sw[sw["error"] == ""][cols] if "error" in sw else sw[cols]
        if len(show) > 13:
            idx = np.unique(np.linspace(0, len(show) - 1, 13).astype(int))
            show = show.iloc[idx]
        xlab = f"{sp.label}" + (f" [{sp.unit}]" if _utxt(sp.unit) else "")
        show = show.rename(columns={"value": xlab, "cost_bulk_EUR": "cost bulk [EUR]", "caco3_kg_per_kg_solids": "CaCO3 [kg/kg solids]", "n_doses": "doses"}).set_index(xlab)
        doc.df_table(show, f"Parametric results per {fu_label} (A1–A3).", index_label=_esc(xlab))
    if opt.include_oat:
        sec += 1
        try:
            oat = oat_sensitivity(scenario, data, category="GWP-total", functional_unit=fu, overrides=overrides, top=opt.oat_top)
        except Exception:  # noqa: BLE001
            oat = pd.DataFrame()
        if len(oat):
            f8 = figures.tornado(oat, "GWP-total", unit_gwp, tdir / "tornado.png", top=opt.oat_top)
            doc.h2(f"7.{sec} One-at-a-time sensitivity")
            doc.figure(f8, "Tornado diagram: change of GWP-total when each input is set to the lower (blue) or upper (red) bound of its range "
                           "while all other inputs stay at their central values. 'background' inputs are literature ranges of background factors, "
                           "'parameter' inputs are the ranges of the scale-up parameters.")
            top3 = oat.head(3)
            doc.p(_sub(f"The three inputs with the largest swing are " + "; ".join(
                f"{_esc(r['input'].replace('industrial.', '').replace('bg:', 'background ').replace('fg:', 'parameter '))} ({fmt(r['result_low'])}–{fmt(r['result_high'])} {unit_gwp}, "
                f"{r['delta_low_%']:+.0f} % / {r['delta_high_%']:+.0f} %)" for _, r in top3.iterrows())
                + f". The central result is {fmt(float(oat['base'].iloc[0]))} {unit_gwp}. Inputs with large swings and poor pedigree scores are the "
                  "priority for primary data collection."))
    if opt.mc is not None:
        sec += 1
        mc = opt.mc
        y = mc.category_samples["GWP-total"]
        p = y.quantile([0.025, 0.25, 0.5, 0.75, 0.975])
        sp_all = mc.spearman("GWP-total", top=40)
        thr = 2.0 / math.sqrt(len(y))
        sp_ = sp_all[sp_all.abs() >= thr].head(12)
        if sp_.empty:
            sp_ = sp_all.head(5)
        f9 = figures.mc_panels(y, unit_gwp, gwp13 if tuple(mc.modules) == ("A1", "A2", "A3") else None, sp_, tdir / "mc.png")
        doc.h2(f"7.{sec} Monte Carlo uncertainty")
        doc.figure(f9, f"Left: distribution of GWP-total from {len(y)} Monte Carlo samples (background factors sampled log-normally from pedigree scores "
                       f"{refs.cite('CIROTH2016', 'MULLER2016')} or log-triangularly within literature ranges; foreground parameters triangularly within "
                       f"their ranges). Right: Spearman rank correlation of the inputs with the result (|ρ| above the noise level 2/√n = {thr:.2f}).")
        doc.p(_sub(f"The median of the distribution is {fmt(p[0.5])} {unit_gwp} with a 95 % interval of {fmt(p[0.025])}–{fmt(p[0.975])} "
                   f"(interquartile range {fmt(p[0.25])}–{fmt(p[0.75])}); the coefficient of variation is {100 * y.std() / y.mean():.0f} %. "
                   f"The result is most sensitive to {', '.join(_esc(i.replace('industrial.', '')) + f' (ρ = {v:+.2f})' for i, v in sp_.head(3).items())}."))
        pct_df = mc.percentiles()
        pct_df.columns = [f"P{q * 100:g}" for q in pct_df.columns]
        pct_df = pct_df.loc[[c for c in CORE if c in pct_df.index]]
        doc.df_table(pct_df, f"Percentiles of the Monte Carlo samples of the core indicators per {fu_label} (modules {' + '.join(mc.modules)}).", index_label="Indicator")
    if sec == 0:
        doc.p("No sensitivity analysis was requested for this report.")

    # ------------------------------------------------------------------------------ 8 cost
    if not data.prices.empty:
        doc.h1("8. Indicative cost")
        cb, cl = cost_summary(res, data, "bulk"), cost_summary(res, data, "lab")
        f10 = figures.cost_by_group(cb["by_group_A1-A3"], cl["by_group_A1-A3"], fu_label, tdir / "cost.png")
        doc.p(_sub(f"The same inventory priced with indicative bulk (technical-grade) prices gives a production cost of <b>{fmt(cb['total_A1-A3'])} EUR</b> per "
                   f"{fu_label} (A1–A3, materials, energy, water, transport and effluent treatment only; labour, capital and margins excluded); with "
                   f"laboratory-grade reagents and media the cost rises to {fmt(cl['total_A1-A3'])} EUR ({fmt(cl['total_A1-A3'] / cb['total_A1-A3']) if cb['total_A1-A3'] else 'n/a'}×), "
                   f"reproducing the observation that culture media dominate the cost of MICP {refs.cite('OMOREGIE2019', 'OTTOVA2026')}. "
                   f"End-of-life handling adds {fmt(cb['total_C1-C4'])} EUR. Prices are indicative and should be replaced by supplier quotations."))
        doc.figure(f10, f"Indicative cost by process group per {fu_label} at bulk and laboratory-grade prices (A1–A3).", width=0.9 * width)
        if cb["unpriced"]:
            doc.p(_esc("Unpriced flows: " + ", ".join(cb["unpriced"])), "small")

    # ------------------------------------------------------------------------------ 9 data quality
    doc.h1("9. Data quality and limitations")
    used = sorted({f.key for f in inv.flows if f.kind == "background"})
    from .uncertainty import pedigree_gsd
    rows = [["Dataset", "Type", "Unit", "GWP factor", "Pedigree (R,C,T,G,F)", "σg", "Source"]]
    for pid in used:
        pr = data.background[pid]
        rows.append([_esc(pr.name[:58]), pr.data_type, pr.unit, fmt(pr.gwp_any), ",".join(map(str, pr.pedigree)), f"{pedigree_gsd(pr.pedigree, pr.basic_uncertainty):.2f}",
                     f"{_esc(pr.source_id)} {refs.cite(pr.source_id)}"])
    doc.table(rows, "Background datasets used by the inventory with their pedigree scores (1 = best, 5 = worst) and the resulting geometric standard deviation σg "
                    f"{refs.cite('CIROTH2016')}.", [0.36 * width, 0.1 * width, 0.06 * width, 0.1 * width, 0.14 * width, 0.06 * width, 0.18 * width])
    proxy = {c: v for c, v in res.proxy_filled.items() if v and c in CORE}
    miss = {c: v for c, v in res.missing.items() if v and c in CORE}
    bad = [pid for pid in used if max(data.background[pid].pedigree) >= 4]
    proxy_sets = sorted({pid for v in proxy.values() for pid in v})
    doc.p(_sub(
        f"The climate-change indicator is covered natively for {pct(res.coverage_native.get('GWP-total', float('nan')))} of the background inventory. "
        + (f"{len(proxy)} of the 13 core categories rely partly on proxy profiles, i.e. the non-GWP factors of a dataset scaled from a similar dataset "
           f"by the ratio of the GWP values; the datasets concerned are {_esc(', '.join(proxy_sets[:10]))}{' …' if len(proxy_sets) > 10 else ''} "
           f"(native coverage of acidification {pct(res.coverage_native.get('AP', float('nan')))}, of water use {pct(res.coverage_native.get('WDP', float('nan')))}). " if proxy else "")
        + (f"Factors are missing for: {_esc('; '.join(f'{c}: ' + ', '.join(v[:4]) for c, v in list(miss.items())[:3]))}. " if miss else "")
        + (f"Datasets with a pedigree score of 4 or worse in at least one dimension: {_esc(', '.join(bad[:8]))}{' …' if len(bad) > 8 else ''}. " if bad else "")
        + "The following limitations apply:"))
    doc.bullets([_sub(x) for x in [
        "<b>Ex-ante character.</b> Yields, strengths and dosing are those of laboratory specimens; the industrial energy model (curing chamber, "
        "sterilisation with heat recovery, fermentation, effluent treatment) is an engineering estimate whose parameters carry the ranges used in Section 7. "
        "Learning effects, process integration and by-product valorisation at full scale are not anticipated beyond the explicit options.",
        "<b>Media and chemicals.</b> The footprints of complex media components (peptones, yeast extract, feather hydrolysate) rest on literature and proxy "
        f"values with wide ranges; they are the dominant uncertainty of the non-ureolytic routes {refs.cite('PORTER2021', 'OTTOVA2026')}.",
        "<b>Nitrogen emissions.</b> The split of the released nitrogen into ammonium, ammonia and nitrous oxide is parameterised, not measured; the N2O share "
        f"is a conservative literature-based assumption {refs.cite('IPCC2019')}. Measurements of the effluent composition and of gaseous emissions are recommended.",
        "<b>Carbonation.</b> The uptake by portlandite carbonation is credited within the life cycle (EN 16757 convention); the assumed fraction should be verified by "
        "thermogravimetry on aged specimens.",
        "<b>Functional equivalence.</b> Comparisons per kg or per m3 neglect differences in strength, durability and thermal properties; the per m3·MPa unit corrects "
        "for strength only. Benchmarks are generic EPD/ÖKOBAUDAT datasets with their own system boundaries.",
        "<b>Impact coverage.</b> The additional indicators (toxicity, particulate matter, ionising radiation, land use) are not declared by all generic datasets "
        "and are reported for information only.",
    ]])

    # ------------------------------------------------------------------------------ 10 conclusions
    doc.h1("10. Interpretation and conclusions")
    concl = []
    concl.append(f"The cradle-to-gate climate-change impact of the scenario is {fmt(gwp13)} {unit_gwp} per {fu_label} ({fmt(gwp13 + gwpc + gwpd)} including "
                 f"end of life and credits); {_top_text(shares_gwp, 2)} dominate the result.")
    if ref_kg is not None and ratio_gwp == ratio_gwp:
        concl.append(f"Per kg of product the impact is {abs(100 * (ratio_gwp - 1)):.0f} % {'below' if ratio_gwp < 1 else 'above'} the reference product "
                     f"{bname(ref_b)}; the comparison per m3 and per unit of strength (Table {tab_comp}) should be consulted before drawing conclusions on substitution.")
    if meta.get("pathway") == "ureolytic" and meta.get("urea_to_ca_molar_ratio"):
        r = float(meta["urea_to_ca_molar_ratio"])
        if r > 1.5:
            concl.append(f"The urea : Ca molar ratio of {fmt(r)} is far above the stoichiometric value of 1; the excess urea is hydrolysed to ammonium/ammonia "
                         f"without precipitating CaCO3 and causes {pct(float(shares_ap.get('Direct process emissions', 0)))} of the acidification. Stoichiometric dosing, "
                         f"recirculation of the solution and ammonia stripping are the first optimisation steps {refs.cite('GOWTHAMAN2022', 'LEE2019')}.")
    if float(meta.get("caco3_precipitated_kg_per_kg_solids", 0)) < 0.01 and float(meta.get("gypsum_fraction", 0) or 0) > 0:
        concl.append("The microbially precipitated CaCO3 is below 1 wt% of the solids: in the gypsum-promoted recipe the bacteria act as a modifier of the "
                     "ettringite-based binder, and the environmental benefit of the biological step must be justified by strength or durability gains.")
    if shares_gwp.get("Cultivation: media", 0) + shares_gwp.get("Biocementation: nutrient medium", 0) > 0.3:
        concl.append("Culture media are the main lever: reducing the medium strength, replacing peptone/yeast extract by hydrolysed by-products (feather "
                     f"hydrolysate, corn steep liquor) and re-using the biocementation solution lower both impacts and cost {refs.cite('OTTOVA2026', 'YOOSATHAPORN2016', 'ACHAL2009')}.")
    if shares_gwp.get("Curing: heat", 0) > 0.15:
        concl.append("Curing heat is a major contributor: lower curing temperatures, better chamber insulation, waste-heat use or ambient curing in the warm "
                     "season would reduce it substantially (see the tornado diagram).")
    if opt.sweep is not None and opt.sweep_parameter is not None:
        d = describe_sweep(opt.sweep, "GWP-total")
        if d:
            concl.append(f"Within the investigated limits of <i>{_esc(opt.sweep_parameter.label)}</i> the climate-change result {d['monotonic']} by "
                         f"{100 * d['relative_span']:.0f} %, with the minimum at {fmt(d['x_of_y_min'])}{_esc(_utxt(opt.sweep_parameter.unit))}.")
    concl.append("Priority data needs are the measured composition of the effluent and off-gas (nitrogen species), the actual curing energy of a pilot "
                 "chamber, the footprint of the media components from suppliers and the strength and durability of full-size blocks.")
    doc.bullets([_sub(c) for c in concl])
    if opt.notes:
        doc.h2("Notes")
        doc.p(_esc(opt.notes))

    # ------------------------------------------------------------------------------ references
    doc.h1("References")
    for n, cit in refs.entries():
        doc.p(f"[{n}] {_esc(cit)}", "ref")

    # ------------------------------------------------------------------------------ build
    def _on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColorRGB(0.35, 0.35, 0.35)
        head = title if len(title) <= 70 else title[:67].rstrip() + "…"
        canvas.drawString(margin, page_h - 12 * mm, f"{head} · {scenario}" if len(head) + len(scenario) < 95 else head)
        canvas.drawRightString(page_w - margin, page_h - 12 * mm, f"micp-lca {__version__} · {today}")
        canvas.drawCentredString(page_w / 2, 10 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    pdf = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=20 * mm, bottomMargin=18 * mm,
                            title=title, author=opt.author or "micp-lca", subject=f"LCA report of scenario {scenario}")
    pdf.build(doc.story, onFirstPage=_on_page, onLaterPages=_on_page)
    tmp.cleanup()
    return out_path
