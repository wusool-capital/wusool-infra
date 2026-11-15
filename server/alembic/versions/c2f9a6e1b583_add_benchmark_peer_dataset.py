"""add the benchmark peer dataset tables and seed them (2026-11-15)

Moves the GCC SME Benchmark's bands, metric weights and peer cuts out of
`benchmark_dataset.py` so advisors can edit them. The seed is the dataset as
it stood on 2026-08-17 (version 1); it is embedded here, not imported, so the
migration still runs once that file is gone.

Revision ID: c2f9a6e1b583
Revises: b7e1c4d8a203
Create Date: 2026-11-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f9a6e1b583"
down_revision: str | Sequence[str] | None = "b7e1c4d8a203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_BY = "seed"

# [id, position, label, max_usd, ebitda_adj, rev_emp_mult, rent_mult]
_BANDS: list[tuple[str, int, str, float | None, float, float, float]] = [
    ("micro", 0, "Under USD 545k", 545000, -3, 0.8, 1.25),
    ("small", 1, "USD 545k to 2.7m", 2725000, 0, 1, 1),
    ("mid", 2, "USD 2.7m to 8.2m", 8170000, 2, 1.2, 0.88),
    ("upper", 3, "USD 8.2m and above", None, 4, 1.4, 0.82),
]

# [mode, key, position, label, unit, higher_is_better, weight, observed]
_METRICS: list[tuple[str, str, int, str, str, bool, int, bool | None]] = [
    ("sme", "ebitda", 0, "Operating profit margin", "%", True, 25, None),
    ("sme", "growth", 1, "Revenue growth", "%", True, 15, None),
    ("sme", "revEmp", 2, "Revenue per employee", "k", True, 15, None),
    ("sme", "conc", 3, "Customer concentration", "%", False, 15, None),
    ("sme", "gm", 4, "Gross margin", "%", True, 10, None),
    ("sme", "rent", 5, "Premises cost", "%", False, 10, None),
    ("sme", "recur", 6, "Contracted revenue", "%", True, 10, None),
    ("tech", "growth", 0, "Revenue growth", "%", True, 25, True),
    ("tech", "capEff", 1, "Revenue per $ raised", "x", True, 20, True),
    ("tech", "revScale", 2, "Revenue for stage", "$", True, 15, True),
    ("tech", "gm", 3, "Gross margin", "%", True, 15, False),
    ("tech", "recur", 4, "Recurring revenue", "%", True, 15, False),
    ("tech", "conc", 5, "Customer concentration", "%", False, 10, False),
]

# [mode, key, label, sample_size, multi_site, b2b, anchors by metric: [p10..p90]]
_CUTS: list[tuple[str, str, str, int, bool, bool, dict[str, list[float]]]] = [
    (
        "sme",
        "restaurant",
        "Restaurant or cafe",
        64,
        True,
        False,
        {
            "ebitda": [2, 7, 12, 18, 25],
            "gm": [55, 60, 65, 70, 74],
            "rent": [8, 11, 15, 20, 26],
            "revEmp": [33, 46, 63, 84, 114],
            "growth": [-8, 0, 7, 15, 28],
            "conc": [2, 3, 5, 10, 20],
            "recur": [0, 1, 5, 12, 25],
            "dso": [0, 2, 5, 12, 25],
        },
    ),
    (
        "sme",
        "salon",
        "Beauty salon or spa",
        48,
        True,
        False,
        {
            "ebitda": [3, 8, 14, 21, 28],
            "gm": [62, 68, 74, 79, 84],
            "rent": [10, 14, 19, 25, 32],
            "revEmp": [25, 35, 48, 65, 87],
            "growth": [-5, 2, 8, 16, 28],
            "conc": [2, 3, 5, 9, 18],
            "recur": [5, 15, 28, 42, 58],
            "dso": [0, 1, 4, 10, 20],
        },
    ),
    (
        "sme",
        "aesthetics",
        "Aesthetics or dermatology clinic",
        37,
        True,
        False,
        {
            "ebitda": [5, 12, 20, 28, 36],
            "gm": [58, 65, 71, 77, 82],
            "rent": [7, 10, 14, 19, 25],
            "revEmp": [60, 90, 123, 169, 231],
            "growth": [-2, 5, 14, 25, 40],
            "conc": [2, 4, 7, 13, 24],
            "recur": [5, 12, 25, 40, 55],
            "dso": [0, 3, 8, 18, 35],
        },
    ),
    (
        "sme",
        "medical",
        "Medical or dental clinic",
        41,
        True,
        False,
        {
            "ebitda": [4, 10, 17, 25, 33],
            "gm": [55, 62, 68, 74, 79],
            "rent": [6, 9, 12, 17, 23],
            "revEmp": [68, 101, 136, 185, 245],
            "growth": [0, 4, 10, 18, 30],
            "conc": [5, 10, 18, 32, 50],
            "recur": [5, 15, 30, 45, 60],
            "dso": [10, 25, 45, 70, 105],
        },
    ),
    (
        "sme",
        "auto",
        "Auto garage, service or detailing",
        52,
        True,
        False,
        {
            "ebitda": [3, 8, 14, 21, 29],
            "gm": [38, 46, 53, 60, 67],
            "rent": [5, 8, 11, 15, 21],
            "revEmp": [41, 60, 82, 112, 152],
            "growth": [-4, 2, 8, 16, 26],
            "conc": [3, 6, 12, 25, 45],
            "recur": [3, 8, 18, 32, 50],
            "dso": [2, 8, 20, 40, 70],
        },
    ),
    (
        "sme",
        "fitness",
        "Gym or fitness studio",
        29,
        True,
        False,
        {
            "ebitda": [2, 9, 16, 24, 33],
            "gm": [63, 70, 76, 81, 86],
            "rent": [11, 15, 20, 26, 33],
            "revEmp": [38, 57, 79, 109, 147],
            "growth": [-3, 4, 11, 20, 33],
            "conc": [2, 3, 5, 9, 17],
            "recur": [60, 70, 80, 88, 93],
            "dso": [0, 1, 3, 8, 16],
        },
    ),
    (
        "sme",
        "nursery",
        "Nursery or early years school",
        24,
        True,
        False,
        {
            "ebitda": [4, 11, 19, 27, 35],
            "gm": [45, 52, 58, 64, 70],
            "rent": [9, 13, 17, 23, 29],
            "revEmp": [27, 37, 48, 63, 82],
            "growth": [0, 3, 8, 14, 24],
            "conc": [2, 3, 5, 8, 15],
            "recur": [70, 80, 88, 93, 96],
            "dso": [3, 8, 15, 28, 45],
        },
    ),
    (
        "sme",
        "training",
        "Training or education centre",
        22,
        True,
        False,
        {
            "ebitda": [2, 8, 15, 23, 31],
            "gm": [50, 58, 65, 72, 78],
            "rent": [7, 10, 14, 19, 25],
            "revEmp": [30, 44, 60, 82, 109],
            "growth": [-5, 2, 9, 18, 30],
            "conc": [5, 10, 20, 35, 55],
            "recur": [10, 20, 35, 50, 68],
            "dso": [5, 15, 30, 55, 85],
        },
    ),
    (
        "sme",
        "cleaning",
        "Cleaning, pest control or facilities services",
        46,
        False,
        True,
        {
            "ebitda": [2, 6, 11, 17, 24],
            "gm": [20, 27, 33, 40, 47],
            "rent": [1, 2, 3, 5, 8],
            "revEmp": [11, 15, 20, 26, 35],
            "growth": [-3, 3, 10, 19, 32],
            "conc": [10, 18, 30, 48, 68],
            "recur": [25, 40, 60, 75, 88],
            "dso": [30, 45, 65, 95, 140],
        },
    ),
    (
        "sme",
        "laundry",
        "Laundry or dry cleaning",
        19,
        True,
        False,
        {
            "ebitda": [3, 9, 15, 22, 30],
            "gm": [48, 56, 63, 70, 76],
            "rent": [5, 8, 11, 16, 22],
            "revEmp": [16, 23, 31, 42, 57],
            "growth": [-2, 3, 9, 16, 26],
            "conc": [3, 7, 14, 28, 48],
            "recur": [10, 20, 35, 50, 65],
            "dso": [2, 8, 18, 35, 60],
        },
    ),
    (
        "sme",
        "trading",
        "General trading or distribution",
        71,
        False,
        True,
        {
            "ebitda": [1, 3, 6, 10, 16],
            "gm": [8, 13, 18, 25, 33],
            "rent": [0.5, 1, 2, 4, 6],
            "revEmp": [109, 177, 259, 381, 599],
            "growth": [-8, 0, 7, 16, 30],
            "conc": [12, 22, 35, 52, 72],
            "recur": [5, 15, 30, 50, 70],
            "dso": [35, 55, 80, 115, 160],
        },
    ),
    (
        "sme",
        "contracting",
        "Contracting, fit-out or MEP",
        58,
        False,
        True,
        {
            "ebitda": [0, 4, 9, 15, 22],
            "gm": [10, 16, 21, 28, 35],
            "rent": [0.5, 1.5, 3, 5, 8],
            "revEmp": [49, 76, 103, 142, 204],
            "growth": [-10, 0, 8, 20, 38],
            "conc": [18, 30, 45, 65, 85],
            "recur": [0, 5, 15, 30, 50],
            "dso": [45, 70, 100, 145, 200],
        },
    ),
    (
        "sme",
        "logistics",
        "Logistics, freight or last-mile delivery",
        34,
        False,
        True,
        {
            "ebitda": [1, 5, 10, 16, 23],
            "gm": [15, 22, 28, 35, 43],
            "rent": [2, 3, 5, 8, 12],
            "revEmp": [25, 37, 50, 68, 93],
            "growth": [-4, 3, 11, 21, 35],
            "conc": [12, 22, 35, 55, 75],
            "recur": [20, 35, 55, 72, 85],
            "dso": [30, 45, 65, 95, 135],
        },
    ),
    (
        "sme",
        "grocery",
        "Grocery, supermarket or retail store",
        43,
        True,
        False,
        {
            "ebitda": [0, 2, 5, 9, 14],
            "gm": [13, 18, 23, 28, 34],
            "rent": [3, 5, 7, 10, 14],
            "revEmp": [76, 109, 147, 196, 267],
            "growth": [-5, 0, 5, 11, 20],
            "conc": [2, 3, 5, 10, 20],
            "recur": [0, 1, 5, 12, 25],
            "dso": [0, 2, 6, 15, 35],
        },
    ),
    (
        "sme",
        "ecommerce",
        "E-commerce or D2C brand",
        31,
        False,
        False,
        {
            "ebitda": [-5, 2, 9, 17, 26],
            "gm": [32, 44, 55, 65, 74],
            "rent": [0.5, 1, 2.5, 4.5, 7],
            "revEmp": [82, 131, 191, 272, 408],
            "growth": [-10, 5, 20, 45, 85],
            "conc": [2, 4, 8, 16, 32],
            "recur": [0, 5, 15, 28, 45],
            "dso": [0, 2, 6, 15, 30],
        },
    ),
    (
        "sme",
        "itservices",
        "IT services or managed services",
        27,
        False,
        True,
        {
            "ebitda": [1, 7, 14, 22, 31],
            "gm": [28, 36, 44, 53, 62],
            "rent": [1, 2, 3.5, 6, 9],
            "revEmp": [49, 71, 95, 128, 177],
            "growth": [-3, 4, 13, 24, 40],
            "conc": [12, 20, 33, 50, 70],
            "recur": [20, 35, 55, 70, 85],
            "dso": [30, 45, 65, 95, 135],
        },
    ),
    (
        "sme",
        "agency",
        "Marketing, creative or media agency",
        26,
        False,
        True,
        {
            "ebitda": [0, 6, 13, 21, 30],
            "gm": [35, 45, 54, 63, 72],
            "rent": [2, 3.5, 5.5, 8, 12],
            "revEmp": [49, 68, 93, 125, 169],
            "growth": [-8, 2, 12, 25, 45],
            "conc": [15, 25, 40, 58, 78],
            "recur": [15, 30, 50, 68, 82],
            "dso": [30, 45, 65, 90, 130],
        },
    ),
    (
        "sme",
        "travel",
        "Travel agency or tour operator",
        21,
        False,
        False,
        {
            "ebitda": [0, 4, 10, 17, 25],
            "gm": [12, 20, 30, 45, 60],
            "rent": [2, 3, 5, 8, 12],
            "revEmp": [54, 82, 114, 158, 218],
            "growth": [-5, 4, 13, 24, 40],
            "conc": [8, 15, 26, 45, 68],
            "recur": [0, 5, 15, 30, 50],
            "dso": [10, 22, 40, 65, 100],
        },
    ),
    (
        "sme",
        "realestate",
        "Real estate brokerage or property services",
        25,
        False,
        False,
        {
            "ebitda": [-2, 5, 12, 21, 32],
            "gm": [55, 65, 73, 80, 87],
            "rent": [3, 5, 8, 12, 17],
            "revEmp": [60, 90, 123, 169, 245],
            "growth": [-15, 0, 15, 35, 70],
            "conc": [5, 10, 20, 38, 62],
            "recur": [0, 2, 8, 18, 35],
            "dso": [10, 25, 45, 75, 115],
        },
    ),
    (
        "sme",
        "manufacturing",
        "Light manufacturing or fabrication",
        33,
        False,
        True,
        {
            "ebitda": [1, 5, 11, 18, 26],
            "gm": [18, 25, 32, 40, 49],
            "rent": [2, 3.5, 6, 9, 14],
            "revEmp": [41, 63, 90, 125, 177],
            "growth": [-6, 1, 8, 17, 30],
            "conc": [15, 25, 40, 60, 80],
            "recur": [5, 15, 30, 50, 70],
            "dso": [35, 55, 80, 115, 165],
        },
    ),
    (
        "tech",
        "seed",
        "Seed or pre-Series A",
        15,
        False,
        False,
        {
            "growth": [76, 117, 150, 267, 400],
            "capEff": [0.04, 0.09, 0.21, 0.55, 1.23],
            "revScale": [100000, 150000, 500000, 2750000, 7200000],
            "gm": [30, 45, 60, 72, 82],
            "recur": [6, 20, 42, 64, 82],
            "conc": [10, 20, 35, 55, 76],
            "fwdMult": [2.1, 3.6, 10, 20, 68.7],
        },
    ),
    (
        "tech",
        "seriesa",
        "Series A",
        19,
        False,
        False,
        {
            "growth": [51, 77, 157, 350, 633],
            "capEff": [0.09, 0.15, 0.39, 1.2, 1.81],
            "revScale": [870000, 1000000, 2100000, 9675000, 19326529],
            "gm": [35, 48, 63, 75, 84],
            "recur": [10, 28, 50, 70, 85],
            "conc": [8, 16, 30, 50, 72],
            "fwdMult": [2.3, 4.1, 5, 7.1, 13.5],
        },
    ),
    (
        "tech",
        "seriesb",
        "Series B or later",
        6,
        False,
        False,
        {
            "growth": [50, 52, 120, 197, 221],
            "capEff": [0.35, 0.48, 0.76, 0.97, 1.06],
            "revScale": [3100000, 3950000, 5150000, 8825000, 10600000],
            "gm": [40, 52, 66, 77, 86],
            "recur": [16, 36, 58, 76, 89],
            "conc": [6, 13, 25, 42, 64],
            "fwdMult": [2.9, 4.9, 6.9, 7.8, 8.7],
        },
    ),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "benchmark_bands",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("max_usd", sa.Numeric(), nullable=True),
        sa.Column("ebitda_adj", sa.Numeric(), nullable=False),
        sa.Column("rev_emp_mult", sa.Numeric(), nullable=False),
        sa.Column("rent_mult", sa.Numeric(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("position"),
    )
    op.create_table(
        "benchmark_metrics",
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("higher_is_better", sa.Boolean(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("observed", sa.Boolean(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('sme','tech')", name="benchmark_metrics_mode_check"),
        sa.CheckConstraint("weight >= 0", name="benchmark_metrics_weight_check"),
        sa.PrimaryKeyConstraint("mode", "key"),
    )
    op.create_table(
        "benchmark_peer_cuts",
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("multi_site", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("b2b", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('sme','tech')", name="benchmark_peer_cuts_mode_check"),
        sa.PrimaryKeyConstraint("mode", "key"),
    )
    op.create_table(
        "benchmark_anchors",
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("peer_key", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("p10", sa.Numeric(), nullable=False),
        sa.Column("p25", sa.Numeric(), nullable=False),
        sa.Column("p50", sa.Numeric(), nullable=False),
        sa.Column("p75", sa.Numeric(), nullable=False),
        sa.Column("p90", sa.Numeric(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "p10 <= p25 AND p25 <= p50 AND p50 <= p75 AND p75 <= p90",
            name="benchmark_anchors_ordered_check",
        ),
        sa.ForeignKeyConstraint(
            ["mode", "peer_key"],
            ["benchmark_peer_cuts.mode", "benchmark_peer_cuts.key"],
            name="benchmark_anchors_peer_cut_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("mode", "peer_key", "metric"),
    )
    op.create_table(
        "benchmark_dataset_version",
        sa.Column("id", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="benchmark_dataset_version_single_row"),
        sa.PrimaryKeyConstraint("id"),
    )

    bind = op.get_bind()
    for band_id, position, label, max_usd, ebitda_adj, rev_emp_mult, rent_mult in _BANDS:
        bind.execute(
            sa.text(
                "INSERT INTO benchmark_bands (id, position, label, max_usd, ebitda_adj,"
                " rev_emp_mult, rent_mult, updated_by) VALUES (:id, :position, :label,"
                " :max_usd, :ebitda_adj, :rev_emp_mult, :rent_mult, :by)"
            ),
            {
                "id": band_id,
                "position": position,
                "label": label,
                "max_usd": max_usd,
                "ebitda_adj": ebitda_adj,
                "rev_emp_mult": rev_emp_mult,
                "rent_mult": rent_mult,
                "by": _SEED_BY,
            },
        )
    for mode, key, position, label, unit, higher, weight, observed in _METRICS:
        bind.execute(
            sa.text(
                "INSERT INTO benchmark_metrics (mode, key, position, label, unit,"
                " higher_is_better, weight, observed, updated_by) VALUES (:mode, :key,"
                " :position, :label, :unit, :higher, :weight, :observed, :by)"
            ),
            {
                "mode": mode,
                "key": key,
                "position": position,
                "label": label,
                "unit": unit,
                "higher": higher,
                "weight": weight,
                "observed": observed,
                "by": _SEED_BY,
            },
        )
    for mode, key, label, sample_size, multi_site, b2b, anchors in _CUTS:
        bind.execute(
            sa.text(
                "INSERT INTO benchmark_peer_cuts (mode, key, label, sample_size, multi_site,"
                " b2b, updated_by) VALUES (:mode, :key, :label, :n, :multi_site, :b2b, :by)"
            ),
            {
                "mode": mode,
                "key": key,
                "label": label,
                "n": sample_size,
                "multi_site": multi_site,
                "b2b": b2b,
                "by": _SEED_BY,
            },
        )
        for metric, (p10, p25, p50, p75, p90) in anchors.items():
            bind.execute(
                sa.text(
                    "INSERT INTO benchmark_anchors (mode, peer_key, metric, p10, p25, p50, p75,"
                    " p90, updated_by) VALUES (:mode, :key, :metric, :p10, :p25, :p50, :p75,"
                    " :p90, :by)"
                ),
                {
                    "mode": mode,
                    "key": key,
                    "metric": metric,
                    "p10": p10,
                    "p25": p25,
                    "p50": p50,
                    "p75": p75,
                    "p90": p90,
                    "by": _SEED_BY,
                },
            )
    bind.execute(
        sa.text(
            "INSERT INTO benchmark_dataset_version (id, version, updated_by) VALUES (1, 1, :by)"
        ),
        {"by": _SEED_BY},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("benchmark_dataset_version")
    op.drop_table("benchmark_anchors")
    op.drop_table("benchmark_peer_cuts")
    op.drop_table("benchmark_metrics")
    op.drop_table("benchmark_bands")
