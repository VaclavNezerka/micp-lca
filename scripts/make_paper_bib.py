"""Assemble paper/micp_lca_paper.bib: selected entries of the group's bibliography + new entries for this paper."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "TeX_paper_template" / "molds_CaCO3.bib"
OUT = ROOT / "paper" / "micp_lca_paper.bib"

REUSE = ["Porter_2021", "Deng_2021", "Omoregie_2019", "Choi_2017", "Whiffin_2004", "Whiffin_2007", "DeJong_2006", "Castanier_1999", "Hammes_2003",
         "Stocks_Fischer_1999", "Mujah_2016", "Dhami_2013", "Dhami_2017", "Ivanov_2019", "Achal_2010", "Achal_2011", "Achal_2014", "Yoosathaporn_2016",
         "Cheng_2018", "Cheng_2020", "Jonkers_2010", "De_Muynck_2010", "Wiktor_2011", "Seifan_2016", "Anbu_2016", "Nezerka_2023_MICP-review",
         "Nezerka_2023_RCF_blocks", "Nezerka_2020_RCF-shrinkage", "Prosek_2020_RCF", "Holecek_2023_MICP_study", "Holecek_2024_micromechanics",
         "Klikova_2025_cultivation", "Stabnikov_2015", "Naveed_2020", "Rajasekar_2021", "Zhu_2016", "Wang_2022_RCF_activation", "Liu_2014_RCF",
         "Chu_2012", "Martinez_2018", "Mitchell_2019", "Fu_2023", "Rahman_2020", "Lee_2018_biocement", "Wang_2017", "Liu_2021", "Ma_2013",
         "Ouyang_2022", "Xu_2021", "Zhao_2021", "Yu_2021", "ChenHJ_2019a", "Li_2020_SCMs", "Zhang_2022", "Aytekin_2023", "Kumari_2014"]

# Corrections applied to reused entries after verification against Crossref / the publishers' pages (September 2026):
# the year is that of the printed volume, and the thesis carries its repository URL.
FIXES = {
    "Mujah_2016": [("year = 2016,", "year = 2017,")],
    "Cheng_2018": [("year = 2018,", "year = 2019,")],
    "Holecek_2024_micromechanics": [("year={2024},", "year={2025},"), ("pages={75\u201384}", "pages={75--84}")],
    "Castanier_1999": [("{\\textemdash}", "--")],
    "Whiffin_2004": [("type={{PhD} thesis}", "type={{PhD} thesis},\n  note={\\url{https://researchportal.murdoch.edu.au/esploro/outputs/doctoral/Microbial-CaCO3-precipitation-for-the-production/991005540291407891}}")],
}

NEW = r"""
@article{Klikova_2025_CCC,
  author  = {Klikov{\'a}, Krist{\'y}na and Hole{\v{c}}ek, Petr and Ko{\v{n}}{\'a}kov{\'a}, Dana and Stiborov{\'a}, Hana and Ne{\v{z}}erka, V{\'a}clav},
  title   = {Exploiting \textit{Bacillus pseudofirmus} and \textit{Bacillus cohnii} to promote {CaCO}$_3$ and {AFt} phase formation for stabilizing waste concrete fines},
  journal = {Cement and Concrete Composites},
  volume  = {155},
  pages   = {105839},
  year    = {2025},
  doi     = {10.1016/j.cemconcomp.2024.105839}
}
@article{Klikova_2025_fungal,
  author  = {Klikov{\'a}, Krist{\'y}na and Hole{\v{c}}ek, Petr and H{\'a}ngocov{\'a}, Jana and Ko{\v{n}}{\'a}kov{\'a}, Dana and Ne{\v{z}}erka, V{\'a}clav and Stiborov{\'a}, Hana},
  title   = {Fungal biomineralization potential for stabilization of waste powders},
  journal = {Journal of Environmental Chemical Engineering},
  volume  = {13},
  pages   = {119335},
  year    = {2025},
  doi     = {10.1016/j.jece.2025.119335}
}
@article{Ottova_2026_feather,
  author  = {Ottov{\'a}, Henrietta and Mal{\'i}kov{\'a}, Barbora and Ne{\v{z}}erka, V{\'a}clav and Hole{\v{c}}ek, Petr and Ko{\v{n}}{\'a}kov{\'a}, Dana and Stiborov{\'a}, Hana},
  title   = {Optimizing feather hydrolysate via machine learning for microbial recycling of waste concrete fines},
  journal = {Journal of Chemical Technology \& Biotechnology},
  year    = {2026},
  doi     = {10.1002/jctb.70172}
}
@unpublished{Nezerka_2026_gypsum,
  author  = {Ne{\v{z}}erka, V{\'a}clav and Klikov{\'a}, Krist{\'y}na and Hole{\v{c}}ek, Petr and Ko{\v{n}}{\'a}kov{\'a}, Dana and Stiborov{\'a}, Hana},
  title   = {Gypsum-promoted non-ureolytic biocementation of heterogeneous demolition residues by sulfate-bearing mineral formation},
  note    = {Preprint submitted to Construction and Building Materials},
  year    = {2026}
}
@article{Alotaibi_2022,
  author  = {Alotaibi, Emran and Arab, Mohamed G. and Abdallah, Mohamed and Nassif, Nadia and Omar, Maher},
  title   = {Life cycle assessment of biocemented sands using enzyme induced carbonate precipitation ({EICP}) for soil stabilization applications},
  journal = {Scientific Reports},
  volume  = {12},
  pages   = {6032},
  year    = {2022},
  doi     = {10.1038/s41598-022-09723-7}
}
@article{Raymond_2025,
  author  = {Raymond, Alena J. and DeJong, Jason T. and Gomez, Michael G. and Kendall, Alissa and San Pablo, Alexandra C. M. and Lee, Minyong and Graddy, Charles M. R. and Nelson, Douglas C.},
  title   = {Life cycle sustainability assessment of microbially induced calcium carbonate precipitation ({MICP}) soil improvement techniques},
  journal = {Applied Sciences},
  volume  = {15},
  pages   = {1059},
  year    = {2025},
  doi     = {10.3390/app15031059}
}
@article{vanPaassen_2010,
  author  = {van Paassen, Leon A. and Ghose, Ranajit and van der Linden, Thomas J. M. and van der Star, Wouter R. L. and van Loosdrecht, Mark C. M.},
  title   = {Quantifying biomediated ground improvement by ureolysis: large-scale biogrout experiment},
  journal = {Journal of Geotechnical and Geoenvironmental Engineering},
  volume  = {136},
  pages   = {1721--1728},
  year    = {2010},
  doi     = {10.1061/(ASCE)GT.1943-5606.0000382}
}
@article{Lee_2019_ammonium,
  author  = {Lee, Minyong and Gomez, Michael G. and San Pablo, Alexandra C. M. and Kolbus, Colin M. and Graddy, Charles M. R. and DeJong, Jason T. and Nelson, Douglas C.},
  title   = {Investigating ammonium by-product removal for ureolytic bio-cementation using meter-scale experiments},
  journal = {Scientific Reports},
  volume  = {9},
  pages   = {18313},
  year    = {2019},
  doi     = {10.1038/s41598-019-54666-1}
}
@article{Gowthaman_2022_struvite,
  author  = {Gowthaman, Sivakumar and Mohsenzadeh, Ali and Nakashima, Kazunori and Kawasaki, Satoru},
  title   = {Removal of ammonium by-products from the effluent of bio-cementation system through struvite precipitation},
  journal = {Materials Today: Proceedings},
  volume  = {61},
  pages   = {243--249},
  year    = {2022},
  doi     = {10.1016/j.matpr.2021.09.013}
}
@article{Achal_2009_LML,
  author  = {Achal, Varenyam and Mukherjee, Abhijit and Basu, P. C. and Reddy, M. Sudhakara},
  title   = {Lactose mother liquor as an alternative nutrient source for microbial concrete production by \textit{Sporosarcina pasteurii}},
  journal = {Journal of Industrial Microbiology \& Biotechnology},
  volume  = {36},
  pages   = {433--438},
  year    = {2009},
  doi     = {10.1007/s10295-008-0514-7}
}
@article{Piccinno_2016,
  author  = {Piccinno, Fabiano and Hischier, Roland and Seeger, Stefan and Som, Claudia},
  title   = {From laboratory to industrial scale: a scale-up framework for chemical processes in life cycle assessment studies},
  journal = {Journal of Cleaner Production},
  volume  = {135},
  pages   = {1085--1097},
  year    = {2016},
  doi     = {10.1016/j.jclepro.2016.06.164}
}
@article{Tsoy_2020,
  author  = {Tsoy, Nadezhda and Steubing, Bernhard and van der Giesen, Coen and Guin{\'e}e, Jeroen},
  title   = {Upscaling methods used in ex ante life cycle assessment of emerging technologies: a review},
  journal = {The International Journal of Life Cycle Assessment},
  volume  = {25},
  pages   = {1680--1692},
  year    = {2020},
  doi     = {10.1007/s11367-020-01796-8}
}
@article{vanderGiesen_2020,
  author  = {van der Giesen, Coen and Cucurachi, Stefano and Guin{\'e}e, Jeroen and Kramer, Gert Jan and Tukker, Arnold},
  title   = {A critical view on the current application of {LCA} for new technologies and recommendations for improved practice},
  journal = {Journal of Cleaner Production},
  volume  = {259},
  pages   = {120904},
  year    = {2020},
  doi     = {10.1016/j.jclepro.2020.120904}
}
@article{Thonemann_2020,
  author  = {Thonemann, Nils and Schulte, Anna and Maga, Daniel},
  title   = {How to conduct prospective life cycle assessment for emerging technologies? {A} systematic review and methodological guidance},
  journal = {Sustainability},
  volume  = {12},
  pages   = {1192},
  year    = {2020},
  doi     = {10.3390/su12031192}
}
@article{Bergerson_2020,
  author  = {Bergerson, Joule A. and Brandt, Adam and Cresko, Joe and Carbajales-Dale, Michael and MacLean, Heather L. and Matthews, H. Scott and McCoy, Sean and McManus, Marcelle and Miller, Sabbie A. and Morrow, William R. and Posen, I. Daniel and Seager, Thomas and Skone, Timothy and Sleep, Sylvia},
  title   = {Life cycle assessment of emerging technologies: evaluation techniques at different stages of market and technical maturity},
  journal = {Journal of Industrial Ecology},
  volume  = {24},
  pages   = {11--25},
  year    = {2020},
  doi     = {10.1111/jiec.12954}
}
@article{Cucurachi_2018,
  author  = {Cucurachi, Stefano and van der Giesen, Coen and Guin{\'e}e, Jeroen},
  title   = {Ex-ante {LCA} of emerging technologies},
  journal = {Procedia CIRP},
  volume  = {69},
  pages   = {463--468},
  year    = {2018},
  doi     = {10.1016/j.procir.2017.11.005}
}
@article{Arvidsson_2018,
  author  = {Arvidsson, Rickard and Tillman, Anne-Marie and Sand{\'e}n, Bj{\"o}rn A. and Janssen, Matty and Nordel{\"o}f, Anders and Kushnir, Duncan and Molander, Sverker},
  title   = {Environmental assessment of emerging technologies: recommendations for prospective {LCA}},
  journal = {Journal of Industrial Ecology},
  volume  = {22},
  pages   = {1286--1294},
  year    = {2018},
  doi     = {10.1111/jiec.12690}
}
@article{Weidema_1996,
  author  = {Weidema, Bo P. and Wesn{\ae}s, Marianne S.},
  title   = {Data quality management for life cycle inventories -- an example of using data quality indicators},
  journal = {Journal of Cleaner Production},
  volume  = {4},
  pages   = {167--174},
  year    = {1996},
  doi     = {10.1016/S0959-6526(96)00043-1}
}
@article{Ciroth_2016,
  author  = {Ciroth, Andreas and Muller, St{\'e}phanie and Weidema, Bo and Lesage, Pascal},
  title   = {Empirically based uncertainty factors for the pedigree matrix in ecoinvent},
  journal = {The International Journal of Life Cycle Assessment},
  volume  = {21},
  pages   = {1338--1348},
  year    = {2016},
  doi     = {10.1007/s11367-013-0670-5}
}
@article{Muller_2016,
  author  = {Muller, St{\'e}phanie and Lesage, Pascal and Ciroth, Andreas and Mutel, Christopher and Weidema, Bo P. and Samson, R{\'e}jean},
  title   = {The application of the pedigree approach to the distributions foreseen in ecoinvent v3},
  journal = {The International Journal of Life Cycle Assessment},
  volume  = {21},
  pages   = {1327--1337},
  year    = {2016},
  doi     = {10.1007/s11367-014-0759-5}
}
@article{Mutel_2017,
  author  = {Mutel, Christopher},
  title   = {Brightway: an open source framework for life cycle assessment},
  journal = {Journal of Open Source Software},
  volume  = {2},
  pages   = {236},
  year    = {2017},
  doi     = {10.21105/joss.00236}
}
@article{Wernet_2016,
  author  = {Wernet, Gregor and Bauer, Christian and Steubing, Bernhard and Reinhard, J{\"u}rgen and Moreno-Ruiz, Emilia and Weidema, Bo},
  title   = {The ecoinvent database version 3 (part {I}): overview and methodology},
  journal = {The International Journal of Life Cycle Assessment},
  volume  = {21},
  pages   = {1218--1230},
  year    = {2016},
  doi     = {10.1007/s11367-016-1087-8}
}
@techreport{FertilizersEurope_2018,
  author      = {{Fertilizers Europe}},
  title       = {The carbon footprint of fertilizer production: regional reference values},
  institution = {Fertilizers Europe},
  address     = {Brussels},
  year        = {2018},
  note        = {\url{https://www.fertilizerseurope.com/wp-content/uploads/2020/01/The-carbon-footprint-of-fertilizer-production_Regional-reference-values.pdf}}
}
@techreport{Ember_2024,
  author      = {{Ember}},
  title       = {European Electricity Review 2024},
  institution = {Ember},
  year        = {2024},
  note        = {\url{https://ember-energy.org/latest-insights/european-electricity-review-2024/}}
}
@misc{OBD_2024,
  author = {{BMWSB}},
  title  = {{\"O}KOBAUDAT data stock {OBD\_2024\_II}: {EN}~15804+A2 / {EF}~3.1 datasets},
  howpublished = {\url{https://www.oekobaudat.de}},
  year   = {2026},
  note   = {Federal Ministry for Housing, Urban Development and Building, Germany; release 22 July 2026}
}
@techreport{AndreasiBassi_2023,
  author      = {Andreasi Bassi, Susanna and Biganzoli, Fabrizio and Ferrara, Nicola and Amadei, Andrea and Valente, Antonio and Sala, Serenella and Ardente, Fulvio},
  title       = {Updated characterisation and normalisation factors for the {Environmental Footprint} 3.1 method},
  institution = {Publications Office of the European Union},
  address     = {Luxembourg},
  number      = {JRC130796},
  year        = {2023},
  doi         = {10.2760/798894}
}
@misc{PEF_2021,
  author = {{European Commission}},
  title  = {Commission Recommendation ({EU}) 2021/2279 of 15 December 2021 on the use of the {Environmental Footprint} methods to measure and communicate the life cycle environmental performance of products and organisations},
  howpublished = {Official Journal of the European Union L 471, \url{https://eur-lex.europa.eu/eli/reco/2021/2279/oj}},
  year   = {2021}
}
@misc{EN15804,
  author = {{CEN}},
  title  = {{EN} 15804:2012+A2:2019 (+AC:2021) Sustainability of construction works -- Environmental product declarations -- Core rules for the product category of construction products},
  howpublished = {European Committee for Standardization, Brussels},
  year   = {2019}
}
@misc{EN16757,
  author = {{CEN}},
  title  = {{EN} 16757:2022 Sustainability of construction works -- Environmental product declarations -- Product category rules for concrete and concrete elements},
  howpublished = {European Committee for Standardization, Brussels},
  year   = {2022}
}
@misc{ISO14040,
  author = {{ISO}},
  title  = {{ISO} 14040:2006 Environmental management -- Life cycle assessment -- Principles and framework},
  howpublished = {International Organization for Standardization, Geneva},
  year   = {2006}
}
@misc{ISO14044,
  author = {{ISO}},
  title  = {{ISO} 14044:2006 (+A1:2017, +A2:2020) Environmental management -- Life cycle assessment -- Requirements and guidelines},
  howpublished = {International Organization for Standardization, Geneva},
  year   = {2006}
}
@misc{ISO14067,
  author = {{ISO}},
  title  = {{ISO} 14067:2018 Greenhouse gases -- Carbon footprint of products -- Requirements and guidelines for quantification},
  howpublished = {International Organization for Standardization, Geneva},
  year   = {2018}
}
@techreport{IPCC_2019,
  author      = {{IPCC}},
  title       = {2019 Refinement to the 2006 {IPCC} Guidelines for National Greenhouse Gas Inventories, Volume 4: Agriculture, Forestry and Other Land Use (Chapter 11: {N$_2$O} emissions from managed soils, and {CO$_2$} emissions from lime and urea application)},
  institution = {Intergovernmental Panel on Climate Change},
  address     = {Geneva},
  year        = {2019},
  note        = {\url{https://www.ipcc-nggip.iges.or.jp/public/2019rf/}}
}
@incollection{IPCC_2021,
  author    = {Forster, Piers and Storelvmo, Trude and Armour, Kyle and Collins, William and Dufresne, Jean-Louis and Frame, David and Lunt, Daniel J. and Mauritsen, Thorsten and Palmer, Matthew D. and Watanabe, Masahiro and Wild, Martin and Zhang, Hua},
  title     = {The {Earth}'s energy budget, climate feedbacks, and climate sensitivity},
  booktitle = {Climate Change 2021: The Physical Science Basis. Contribution of Working Group I to the Sixth Assessment Report of the Intergovernmental Panel on Climate Change},
  publisher = {Cambridge University Press},
  address   = {Cambridge, UK and New York, NY, USA},
  year      = {2021},
  pages     = {923--1054},
  doi       = {10.1017/9781009157896.009}
}
@misc{AGRIBALYSE_2025,
  author = {{ADEME}},
  title  = {{AGRIBALYSE} v3.2: environmental impacts of agricultural and food products ({EF}~3.1 method)},
  howpublished = {\url{https://data.ademe.fr/datasets/7yjrtdnoq-ip4mgab1srophe}},
  year   = {2025}
}
@misc{Environdec_3048,
  author = {{Gasbeton}},
  title  = {Environmental Product Declaration {S-P-03048}: {Sysmic Idro} autoclaved aerated concrete blocks},
  howpublished = {EPD International, \url{https://environdec.com/library/epd3048}},
  year   = {2021}
}
@article{Morao_2019,
  author  = {Mor{\~a}o, Ana and de Bie, Fran{\c{c}}ois},
  title   = {Life cycle impact assessment of polylactic acid ({PLA}) produced from sugarcane in {Thailand}},
  journal = {Journal of Polymers and the Environment},
  volume  = {27},
  pages   = {2523--2539},
  year    = {2019},
  doi     = {10.1007/s10924-019-01525-9}
}
@article{Becker_2023,
  author  = {Becker, Martin and Ziemi{\'n}ska-Stolarska, Aleksandra and Markowska, Dorota and L{\"u}tz, Stephan and Rosenthal, Katrin},
  title   = {Comparative life cycle assessment of chemical and biocatalytic 2'3'-cyclic {GMP-AMP} synthesis},
  journal = {ChemSusChem},
  volume  = {16},
  pages   = {e202201629},
  year    = {2023},
  doi     = {10.1002/cssc.202201629}
}
@article{Hunter_2007,
  author  = {Hunter, John D.},
  title   = {Matplotlib: a {2D} graphics environment},
  journal = {Computing in Science \& Engineering},
  volume  = {9},
  pages   = {90--95},
  year    = {2007},
  doi     = {10.1109/MCSE.2007.55}
}
@article{Steubing_2020,
  author  = {Steubing, Bernhard and de Koning, Daniel and Haas, Adrian and Mutel, Christopher Lawrence},
  title   = {The {Activity Browser} -- an open source {LCA} software building on top of the brightway framework},
  journal = {Software Impacts},
  volume  = {3},
  pages   = {100012},
  year    = {2020},
  doi     = {10.1016/j.simpa.2019.100012}
}
@article{Sacchi_2022,
  author  = {Sacchi, Romain and Terlouw, Tom and Siala, Kais and Dirnaichner, Alois and Bauer, Christian and Cox, Brian and Mutel, Chris and Daioglou, Vassilis and Luderer, Gunnar},
  title   = {{PRospective EnvironMental Impact asSEment} (premise): a streamlined approach to producing databases for prospective life cycle assessment using integrated assessment models},
  journal = {Renewable and Sustainable Energy Reviews},
  volume  = {160},
  pages   = {112311},
  year    = {2022},
  doi     = {10.1016/j.rser.2022.112311}
}
@article{Villares_2017,
  author  = {Villares, Miguel and I{\c{s}}{\i}ldar, Arda and van der Giesen, Coen and Guin{\'e}e, Jeroen},
  title   = {Does ex ante application enhance the usefulness of {LCA}? {A} case study on an emerging technology for metal recovery from e-waste},
  journal = {The International Journal of Life Cycle Assessment},
  volume  = {22},
  pages   = {1618--1633},
  year    = {2017},
  doi     = {10.1007/s11367-017-1270-6}
}
@article{Moni_2020,
  author  = {Moni, Sheikh Moniruzzaman and Mahmud, Roksana and High, Karen and Carbajales-Dale, Michael},
  title   = {Life cycle assessment of emerging technologies: a review},
  journal = {Journal of Industrial Ecology},
  volume  = {24},
  pages   = {52--63},
  year    = {2020},
  doi     = {10.1111/jiec.12965}
}
@article{Hellweg_2014,
  author  = {Hellweg, Stefanie and Mil{\`a} i Canals, Lloren{\c{c}}},
  title   = {Emerging approaches, challenges and opportunities in life cycle assessment},
  journal = {Science},
  volume  = {344},
  pages   = {1109--1113},
  year    = {2014},
  doi     = {10.1126/science.1248361}
}
@article{Igos_2019,
  author  = {Igos, Elorri and Benetto, Enrico and Meyer, Rodolphe and Baustert, Paul and Othoniel, Benoit},
  title   = {How to treat uncertainties in life cycle assessment studies?},
  journal = {The International Journal of Life Cycle Assessment},
  volume  = {24},
  pages   = {794--807},
  year    = {2019},
  doi     = {10.1007/s11367-018-1477-1}
}
@article{Scrivener_2018,
  author  = {Scrivener, Karen L. and John, Vanderley M. and Gartner, Ellis M.},
  title   = {Eco-efficient cements: potential economically viable solutions for a low-{CO}$_2$ cement-based materials industry},
  journal = {Cement and Concrete Research},
  volume  = {114},
  pages   = {2--26},
  year    = {2018},
  doi     = {10.1016/j.cemconres.2018.03.015}
}
@article{Monteiro_2017,
  author  = {Monteiro, Paulo J. M. and Miller, Sabbie A. and Horvath, Arpad},
  title   = {Towards sustainable concrete},
  journal = {Nature Materials},
  volume  = {16},
  pages   = {698--699},
  year    = {2017},
  doi     = {10.1038/nmat4930}
}
@article{Miller_2018,
  author  = {Miller, Sabbie A. and Horvath, Arpad and Monteiro, Paulo J. M.},
  title   = {Impacts of booming concrete production on water resources worldwide},
  journal = {Nature Sustainability},
  volume  = {1},
  pages   = {69--76},
  year    = {2018},
  doi     = {10.1038/s41893-017-0009-5}
}
@article{Xiao_2018_RCF,
  author  = {Xiao, Jianzhuang and Ma, Zhiming and Sui, Tongbo and Akbarnezhad, Ali and Duan, Zhenhua},
  title   = {Mechanical properties of concrete mixed with recycled powder produced from construction and demolition waste},
  journal = {Journal of Cleaner Production},
  volume  = {188},
  pages   = {720--731},
  year    = {2018},
  doi     = {10.1016/j.jclepro.2018.03.277}
}
"""


def main() -> None:
    txt = SRC.read_text(encoding="utf-8", errors="replace")
    entries: dict[str, str] = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", txt):
        j = txt.index("{", m.start())
        depth, k = 0, j
        while k < len(txt):
            if txt[k] == "{":
                depth += 1
            elif txt[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        entries[m.group(2)] = txt[m.start():k + 1]
    out = ["% Bibliography of the micp-lca paper: entries reused from the group's bibliography + new entries (scripts/make_paper_bib.py)", ""]
    missing = [k for k in REUSE if k not in entries]
    if missing:
        raise SystemExit(f"missing keys in template bib: {missing}")
    for k in REUSE:
        e = entries[k]
        for a, b in FIXES.get(k, []):
            if a not in e:
                raise SystemExit(f"fix for {k} does not apply: {a!r}")
            e = e.replace(a, b)
        out.append(e)
        out.append("")
    out.append(NEW.strip())
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("written", OUT, "entries:", len(REUSE) + NEW.count("@"))


if __name__ == "__main__":
    main()
