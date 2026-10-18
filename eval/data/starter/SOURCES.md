# Starter set sources and attribution

All three sources are licensed CC BY 4.0. Columns in `columns.jsonl` are sampled values (up to
100 per column) from these datasets; labels in `blind.csv` and `review.csv` are ours.

| Dataset | Creator | License | Link |
| --- | --- | --- | --- |
| GitTables benchmark: column type detection (v1, 2021) | Madelon Hulsebos, Çağatay Demiralp, Paul Groth | CC BY 4.0 | [zenodo.org/records/5706316](https://zenodo.org/records/5706316) |
| Bank Marketing (bank-additional-full.csv) | Sérgio Moro, Paulo Rita, Paulo Cortez | CC BY 4.0 | [archive.ics.uci.edu/dataset/222](https://archive.ics.uci.edu/dataset/222/bank+marketing) |
| Online Retail II (first 20,000 rows of sheet 1) | Daqing Chen | CC BY 4.0 | [archive.ics.uci.edu/dataset/502](https://archive.ics.uci.edu/dataset/502/online+retail+ii) |

Raw downloads live in `data/raw/` (git-ignored, about 48 MB). Rebuild with:

```bash
.venv/bin/python -I -m jeveval.starter build
```
