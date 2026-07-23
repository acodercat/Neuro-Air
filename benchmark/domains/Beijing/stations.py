"""Canonical Beijing station partition.

Single source of truth shared by both the system prompt
(`domains/Beijing/prompts.py`) and benchmark validators in `evals/*/Beijing/`.
Defining the partition once here prevents the documented classification the
agent is given from drifting from what validators score against.
"""

URBAN_STATIONS = [
    "Dongsi",
    "Guanyuan",
    "Wanshouxigong",
    "Tiantan",
    "Nongzhanguan",
    "Aotizhongxin",
]

SUBURBAN_STATIONS = [
    "Changping",
    "Dingling",
    "Huairou",
    "Shunyi",
]

WESTERN_URBAN_STATIONS = [
    "Gucheng",
    "Wanliu",
]

ALL_STATIONS = URBAN_STATIONS + SUBURBAN_STATIONS + WESTERN_URBAN_STATIONS
