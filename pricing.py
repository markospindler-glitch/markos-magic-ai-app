"""Estimated GPT-5.5 workflow pricing table."""

from __future__ import annotations


PRICE_ROWS = [
    {
        "Document length": "500 words",
        "Translation only": "€0.02-€0.03",
        "Translation + proofreading": "€0.05",
        "Full workflow": "€0.08-€0.15",
        "Full workflow + aligned XLIFF": "€0.15-€0.25",
    },
    {
        "Document length": "1,000 words",
        "Translation only": "€0.05-€0.06",
        "Translation + proofreading": "€0.10",
        "Full workflow": "€0.15-€0.30",
        "Full workflow + aligned XLIFF": "€0.25-€0.40",
    },
    {
        "Document length": "2,500 words",
        "Translation only": "€0.12-€0.15",
        "Translation + proofreading": "€0.25",
        "Full workflow": "€0.40-€0.75",
        "Full workflow + aligned XLIFF": "€0.60-€1.00",
    },
    {
        "Document length": "5,000 words",
        "Translation only": "€0.25-€0.30",
        "Translation + proofreading": "€0.50-€0.60",
        "Full workflow": "€0.75-€1.50",
        "Full workflow + aligned XLIFF": "€1.25-€2.00",
    },
    {
        "Document length": "10,000 words",
        "Translation only": "€0.50-€0.60",
        "Translation + proofreading": "€1.00-€1.20",
        "Full workflow": "€1.50-€3.00",
        "Full workflow + aligned XLIFF": "€2.00-€4.00",
    },
    {
        "Document length": "20,000 words",
        "Translation only": "€1.00-€1.20",
        "Translation + proofreading": "€2.00-€2.50",
        "Full workflow": "€3.00-€6.00",
        "Full workflow + aligned XLIFF": "€4.00-€8.00",
    },
    {
        "Document length": "30,000 words",
        "Translation only": "€1.50-€1.80",
        "Translation + proofreading": "€3.00-€3.75",
        "Full workflow": "€4.50-€9.00",
        "Full workflow + aligned XLIFF": "€6.00-€12.00",
    },
]


def pricing_rows() -> list[dict[str, str]]:
    """Return price-list rows for Streamlit display."""
    return PRICE_ROWS
