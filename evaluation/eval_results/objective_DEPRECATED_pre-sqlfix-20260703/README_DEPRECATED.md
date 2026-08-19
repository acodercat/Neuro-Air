# DEPRECATED — do not use

These results were produced **before** the SQL error-classification fix
(the `SQL:Parameterisation` pattern was missing, so 62 psycopg placeholder
errors were misfiled as `Other`).

Consequence: the SQL/tool-interface share of function-calling errors computes
to **40.4%** here, versus the correct **95.6%** (108/113).

Authoritative results: `../objective_hk/objective_metrics.{json,csv}` (2026-07-22).
The manuscript quotes the values from that directory.

Also deprecated for the same reason:
`../objective_hk/objective_metrics.json.pre-sqlfix-20260722.deprecated`
