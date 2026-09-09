"""The GCC SME Benchmark peer dataset — generated, do not hand-edit.

Extracted verbatim from the `DATA` block in `wusool-benchmark.html`, which
is the authority for what the live tool actually computes against.

**Not** from `benchmark-dataset.json` in that repo, which is a stale
pre-conversion copy: it still declares `"currency": "AED"`, carries the
original AED band cuts (2m/10m/30m against the HTML's USD 545k/2.7m/8.2m),
and its `revEmp` anchors are larger by the 3.6725 peg — `restaurant` reads
[120, 170, 230, 310, 420] there against [33, 46, 63, 84, 114] here. Porting
the JSON would have made every revenue-per-employee percentile and every peer
band wrong by 3.67x, with nothing in the output to show it.

Every figure here is USD. `revEmp` is thousands of USD; every other metric
is a percentage, a multiple, or a count, so only `revEmp` and the band cuts
were currency-denominated in the first place.

Anchors are [p10, p25, p50, p75, p90].
"""

from app.modules.lead_magnets.domain.benchmark import Band, MetricSpec, PeerCut

DATASET_VERSION = "1.0"
DATASET_UPDATED = "2026-08-17"


# Revenue bands. The cuts are the original AED 2m / 10m / 30m boundaries
# converted at 3.6725, so the same companies fall in the same peer sets.
BANDS: tuple[Band, ...] = (
    Band(
        id="micro",
        label="Under USD 545k",
        max_usd=545000,
        ebitda_adj=-3,
        rev_emp_mult=0.8,
        rent_mult=1.25,
    ),
    Band(
        id="small",
        label="USD 545k to 2.7m",
        max_usd=2725000,
        ebitda_adj=0,
        rev_emp_mult=1,
        rent_mult=1,
    ),
    Band(
        id="mid",
        label="USD 2.7m to 8.2m",
        max_usd=8170000,
        ebitda_adj=2,
        rev_emp_mult=1.2,
        rent_mult=0.88,
    ),
    Band(
        id="upper",
        label="USD 8.2m and above",
        max_usd=None,
        ebitda_adj=4,
        rev_emp_mult=1.4,
        rent_mult=0.82,
    ),
)

SME_METRICS: dict[str, MetricSpec] = {
    "ebitda": MetricSpec(
        label="Operating profit margin", unit="%", higher_is_better=True, weight=25
    ),
    "growth": MetricSpec(label="Revenue growth", unit="%", higher_is_better=True, weight=15),
    "revEmp": MetricSpec(label="Revenue per employee", unit="k", higher_is_better=True, weight=15),
    "conc": MetricSpec(label="Customer concentration", unit="%", higher_is_better=False, weight=15),
    "gm": MetricSpec(label="Gross margin", unit="%", higher_is_better=True, weight=10),
    "rent": MetricSpec(label="Premises cost", unit="%", higher_is_better=False, weight=10),
    "recur": MetricSpec(label="Contracted revenue", unit="%", higher_is_better=True, weight=10),
}

TECH_METRICS: dict[str, MetricSpec] = {
    "growth": MetricSpec(label="Revenue growth", unit="%", higher_is_better=True, weight=25),
    "capEff": MetricSpec(label="Revenue per $ raised", unit="x", higher_is_better=True, weight=20),
    "revScale": MetricSpec(label="Revenue for stage", unit="$", higher_is_better=True, weight=15),
    "gm": MetricSpec(label="Gross margin", unit="%", higher_is_better=True, weight=15),
    "recur": MetricSpec(label="Recurring revenue", unit="%", higher_is_better=True, weight=15),
    "conc": MetricSpec(label="Customer concentration", unit="%", higher_is_better=False, weight=10),
}

SECTORS: dict[str, PeerCut] = {
    "restaurant": PeerCut(
        label="Restaurant or cafe",
        sample_size=64,
        anchors={
            "ebitda": (2, 7, 12, 18, 25),
            "gm": (55, 60, 65, 70, 74),
            "rent": (8, 11, 15, 20, 26),
            "revEmp": (33, 46, 63, 84, 114),
            "growth": (-8, 0, 7, 15, 28),
            "conc": (2, 3, 5, 10, 20),
            "recur": (0, 1, 5, 12, 25),
            "dso": (0, 2, 5, 12, 25),
        },
        multi_site=True,
        b2b=False,
    ),
    "salon": PeerCut(
        label="Beauty salon or spa",
        sample_size=48,
        anchors={
            "ebitda": (3, 8, 14, 21, 28),
            "gm": (62, 68, 74, 79, 84),
            "rent": (10, 14, 19, 25, 32),
            "revEmp": (25, 35, 48, 65, 87),
            "growth": (-5, 2, 8, 16, 28),
            "conc": (2, 3, 5, 9, 18),
            "recur": (5, 15, 28, 42, 58),
            "dso": (0, 1, 4, 10, 20),
        },
        multi_site=True,
        b2b=False,
    ),
    "aesthetics": PeerCut(
        label="Aesthetics or dermatology clinic",
        sample_size=37,
        anchors={
            "ebitda": (5, 12, 20, 28, 36),
            "gm": (58, 65, 71, 77, 82),
            "rent": (7, 10, 14, 19, 25),
            "revEmp": (60, 90, 123, 169, 231),
            "growth": (-2, 5, 14, 25, 40),
            "conc": (2, 4, 7, 13, 24),
            "recur": (5, 12, 25, 40, 55),
            "dso": (0, 3, 8, 18, 35),
        },
        multi_site=True,
        b2b=False,
    ),
    "medical": PeerCut(
        label="Medical or dental clinic",
        sample_size=41,
        anchors={
            "ebitda": (4, 10, 17, 25, 33),
            "gm": (55, 62, 68, 74, 79),
            "rent": (6, 9, 12, 17, 23),
            "revEmp": (68, 101, 136, 185, 245),
            "growth": (0, 4, 10, 18, 30),
            "conc": (5, 10, 18, 32, 50),
            "recur": (5, 15, 30, 45, 60),
            "dso": (10, 25, 45, 70, 105),
        },
        multi_site=True,
        b2b=False,
    ),
    "auto": PeerCut(
        label="Auto garage, service or detailing",
        sample_size=52,
        anchors={
            "ebitda": (3, 8, 14, 21, 29),
            "gm": (38, 46, 53, 60, 67),
            "rent": (5, 8, 11, 15, 21),
            "revEmp": (41, 60, 82, 112, 152),
            "growth": (-4, 2, 8, 16, 26),
            "conc": (3, 6, 12, 25, 45),
            "recur": (3, 8, 18, 32, 50),
            "dso": (2, 8, 20, 40, 70),
        },
        multi_site=True,
        b2b=False,
    ),
    "fitness": PeerCut(
        label="Gym or fitness studio",
        sample_size=29,
        anchors={
            "ebitda": (2, 9, 16, 24, 33),
            "gm": (63, 70, 76, 81, 86),
            "rent": (11, 15, 20, 26, 33),
            "revEmp": (38, 57, 79, 109, 147),
            "growth": (-3, 4, 11, 20, 33),
            "conc": (2, 3, 5, 9, 17),
            "recur": (60, 70, 80, 88, 93),
            "dso": (0, 1, 3, 8, 16),
        },
        multi_site=True,
        b2b=False,
    ),
    "nursery": PeerCut(
        label="Nursery or early years school",
        sample_size=24,
        anchors={
            "ebitda": (4, 11, 19, 27, 35),
            "gm": (45, 52, 58, 64, 70),
            "rent": (9, 13, 17, 23, 29),
            "revEmp": (27, 37, 48, 63, 82),
            "growth": (0, 3, 8, 14, 24),
            "conc": (2, 3, 5, 8, 15),
            "recur": (70, 80, 88, 93, 96),
            "dso": (3, 8, 15, 28, 45),
        },
        multi_site=True,
        b2b=False,
    ),
    "training": PeerCut(
        label="Training or education centre",
        sample_size=22,
        anchors={
            "ebitda": (2, 8, 15, 23, 31),
            "gm": (50, 58, 65, 72, 78),
            "rent": (7, 10, 14, 19, 25),
            "revEmp": (30, 44, 60, 82, 109),
            "growth": (-5, 2, 9, 18, 30),
            "conc": (5, 10, 20, 35, 55),
            "recur": (10, 20, 35, 50, 68),
            "dso": (5, 15, 30, 55, 85),
        },
        multi_site=True,
        b2b=False,
    ),
    "cleaning": PeerCut(
        label="Cleaning, pest control or facilities services",
        sample_size=46,
        anchors={
            "ebitda": (2, 6, 11, 17, 24),
            "gm": (20, 27, 33, 40, 47),
            "rent": (1, 2, 3, 5, 8),
            "revEmp": (11, 15, 20, 26, 35),
            "growth": (-3, 3, 10, 19, 32),
            "conc": (10, 18, 30, 48, 68),
            "recur": (25, 40, 60, 75, 88),
            "dso": (30, 45, 65, 95, 140),
        },
        multi_site=False,
        b2b=True,
    ),
    "laundry": PeerCut(
        label="Laundry or dry cleaning",
        sample_size=19,
        anchors={
            "ebitda": (3, 9, 15, 22, 30),
            "gm": (48, 56, 63, 70, 76),
            "rent": (5, 8, 11, 16, 22),
            "revEmp": (16, 23, 31, 42, 57),
            "growth": (-2, 3, 9, 16, 26),
            "conc": (3, 7, 14, 28, 48),
            "recur": (10, 20, 35, 50, 65),
            "dso": (2, 8, 18, 35, 60),
        },
        multi_site=True,
        b2b=False,
    ),
    "trading": PeerCut(
        label="General trading or distribution",
        sample_size=71,
        anchors={
            "ebitda": (1, 3, 6, 10, 16),
            "gm": (8, 13, 18, 25, 33),
            "rent": (0.5, 1, 2, 4, 6),
            "revEmp": (109, 177, 259, 381, 599),
            "growth": (-8, 0, 7, 16, 30),
            "conc": (12, 22, 35, 52, 72),
            "recur": (5, 15, 30, 50, 70),
            "dso": (35, 55, 80, 115, 160),
        },
        multi_site=False,
        b2b=True,
    ),
    "contracting": PeerCut(
        label="Contracting, fit-out or MEP",
        sample_size=58,
        anchors={
            "ebitda": (0, 4, 9, 15, 22),
            "gm": (10, 16, 21, 28, 35),
            "rent": (0.5, 1.5, 3, 5, 8),
            "revEmp": (49, 76, 103, 142, 204),
            "growth": (-10, 0, 8, 20, 38),
            "conc": (18, 30, 45, 65, 85),
            "recur": (0, 5, 15, 30, 50),
            "dso": (45, 70, 100, 145, 200),
        },
        multi_site=False,
        b2b=True,
    ),
    "logistics": PeerCut(
        label="Logistics, freight or last-mile delivery",
        sample_size=34,
        anchors={
            "ebitda": (1, 5, 10, 16, 23),
            "gm": (15, 22, 28, 35, 43),
            "rent": (2, 3, 5, 8, 12),
            "revEmp": (25, 37, 50, 68, 93),
            "growth": (-4, 3, 11, 21, 35),
            "conc": (12, 22, 35, 55, 75),
            "recur": (20, 35, 55, 72, 85),
            "dso": (30, 45, 65, 95, 135),
        },
        multi_site=False,
        b2b=True,
    ),
    "grocery": PeerCut(
        label="Grocery, supermarket or retail store",
        sample_size=43,
        anchors={
            "ebitda": (0, 2, 5, 9, 14),
            "gm": (13, 18, 23, 28, 34),
            "rent": (3, 5, 7, 10, 14),
            "revEmp": (76, 109, 147, 196, 267),
            "growth": (-5, 0, 5, 11, 20),
            "conc": (2, 3, 5, 10, 20),
            "recur": (0, 1, 5, 12, 25),
            "dso": (0, 2, 6, 15, 35),
        },
        multi_site=True,
        b2b=False,
    ),
    "ecommerce": PeerCut(
        label="E-commerce or D2C brand",
        sample_size=31,
        anchors={
            "ebitda": (-5, 2, 9, 17, 26),
            "gm": (32, 44, 55, 65, 74),
            "rent": (0.5, 1, 2.5, 4.5, 7),
            "revEmp": (82, 131, 191, 272, 408),
            "growth": (-10, 5, 20, 45, 85),
            "conc": (2, 4, 8, 16, 32),
            "recur": (0, 5, 15, 28, 45),
            "dso": (0, 2, 6, 15, 30),
        },
        multi_site=False,
        b2b=False,
    ),
    "itservices": PeerCut(
        label="IT services or managed services",
        sample_size=27,
        anchors={
            "ebitda": (1, 7, 14, 22, 31),
            "gm": (28, 36, 44, 53, 62),
            "rent": (1, 2, 3.5, 6, 9),
            "revEmp": (49, 71, 95, 128, 177),
            "growth": (-3, 4, 13, 24, 40),
            "conc": (12, 20, 33, 50, 70),
            "recur": (20, 35, 55, 70, 85),
            "dso": (30, 45, 65, 95, 135),
        },
        multi_site=False,
        b2b=True,
    ),
    "agency": PeerCut(
        label="Marketing, creative or media agency",
        sample_size=26,
        anchors={
            "ebitda": (0, 6, 13, 21, 30),
            "gm": (35, 45, 54, 63, 72),
            "rent": (2, 3.5, 5.5, 8, 12),
            "revEmp": (49, 68, 93, 125, 169),
            "growth": (-8, 2, 12, 25, 45),
            "conc": (15, 25, 40, 58, 78),
            "recur": (15, 30, 50, 68, 82),
            "dso": (30, 45, 65, 90, 130),
        },
        multi_site=False,
        b2b=True,
    ),
    "travel": PeerCut(
        label="Travel agency or tour operator",
        sample_size=21,
        anchors={
            "ebitda": (0, 4, 10, 17, 25),
            "gm": (12, 20, 30, 45, 60),
            "rent": (2, 3, 5, 8, 12),
            "revEmp": (54, 82, 114, 158, 218),
            "growth": (-5, 4, 13, 24, 40),
            "conc": (8, 15, 26, 45, 68),
            "recur": (0, 5, 15, 30, 50),
            "dso": (10, 22, 40, 65, 100),
        },
        multi_site=False,
        b2b=False,
    ),
    "realestate": PeerCut(
        label="Real estate brokerage or property services",
        sample_size=25,
        anchors={
            "ebitda": (-2, 5, 12, 21, 32),
            "gm": (55, 65, 73, 80, 87),
            "rent": (3, 5, 8, 12, 17),
            "revEmp": (60, 90, 123, 169, 245),
            "growth": (-15, 0, 15, 35, 70),
            "conc": (5, 10, 20, 38, 62),
            "recur": (0, 2, 8, 18, 35),
            "dso": (10, 25, 45, 75, 115),
        },
        multi_site=False,
        b2b=False,
    ),
    "manufacturing": PeerCut(
        label="Light manufacturing or fabrication",
        sample_size=33,
        anchors={
            "ebitda": (1, 5, 11, 18, 26),
            "gm": (18, 25, 32, 40, 49),
            "rent": (2, 3.5, 6, 9, 14),
            "revEmp": (41, 63, 90, 125, 177),
            "growth": (-6, 1, 8, 17, 30),
            "conc": (15, 25, 40, 60, 80),
            "recur": (5, 15, 30, 50, 70),
            "dso": (35, 55, 80, 115, 165),
        },
        multi_site=False,
        b2b=True,
    ),
}

STAGES: dict[str, PeerCut] = {
    "seed": PeerCut(
        label="Seed or pre-Series A",
        sample_size=15,
        anchors={
            "growth": (76, 117, 150, 267, 400),
            "capEff": (0.04, 0.09, 0.21, 0.55, 1.23),
            "revScale": (100000, 150000, 500000, 2750000, 7200000),
            "gm": (30, 45, 60, 72, 82),
            "recur": (6, 20, 42, 64, 82),
            "conc": (10, 20, 35, 55, 76),
            "fwdMult": (2.1, 3.6, 10, 20, 68.7),
        },
    ),
    "seriesa": PeerCut(
        label="Series A",
        sample_size=19,
        anchors={
            "growth": (51, 77, 157, 350, 633),
            "capEff": (0.09, 0.15, 0.39, 1.2, 1.81),
            "revScale": (870000, 1000000, 2100000, 9675000, 19326529),
            "gm": (35, 48, 63, 75, 84),
            "recur": (10, 28, 50, 70, 85),
            "conc": (8, 16, 30, 50, 72),
            "fwdMult": (2.3, 4.1, 5, 7.1, 13.5),
        },
    ),
    "seriesb": PeerCut(
        label="Series B or later",
        sample_size=6,
        anchors={
            "growth": (50, 52, 120, 197, 221),
            "capEff": (0.35, 0.48, 0.76, 0.97, 1.06),
            "revScale": (3100000, 3950000, 5150000, 8825000, 10600000),
            "gm": (40, 52, 66, 77, 86),
            "recur": (16, 36, 58, 76, 89),
            "conc": (6, 13, 25, 42, 64),
            "fwdMult": (2.9, 4.9, 6.9, 7.8, 8.7),
        },
    ),
}

TECH_SECTOR_LIST: tuple[str, ...] = (
    "AI",
    "SaaS",
    "Fintech",
    "Digital Health",
    "Supply Chain or mobility",
    "FoodTech",
    "E-commerce",
    "Proptech",
    "Edtech",
    "DeepTech or hardware",
    "Other",
)
