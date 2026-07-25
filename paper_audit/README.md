# Manuscript audits

Checks that keep the paper consistent with the artefacts this repository
produces. They exist because the same failure kept recurring: an experiment is
rerun, the CSVs update, and a number left elsewhere in the manuscript quietly
goes stale.

Every one of these found at least one real error in the paper.

## Running them

The manuscript lives outside this repository. Point the audits at it:

```bash
export GNNARRATE_PAPER=/path/to/gnnarrate-paper        # holds submission/main.tex
export GNNARRATE_PLATFORM=/path/to/CLARUS/checkout     # optional; see below
python paper_audit/audit_numbers.py
```

`GNNARRATE_PAPER` defaults to a sibling `gnnarrate-paper` directory.
`GNNARRATE_PLATFORM` is only needed for the cohort-size check, which is skipped
when the platform is absent — the dataset is too large to vendor here.

## What each one does

| Script | Checks |
|---|---|
| `audit_numbers.py` | Every quantitative claim against the released CSVs and JSON. The main defence against stale numbers. |
| `audit_coverage.py` | That *no* numeric literal is unaccounted for — each is verified, structural, or explicitly derived with a written reason. |
| `audit_method.py` | That the method section describes what the code actually does, by reading the package source. |
| `audit_prose.py` | What the numeric audits cannot see: orphaned labels, spelled-out counts that disagree with the data, tables missing a row, terminology variants, search-and-replace leftovers. |
| `audit_escapes.py` | LaTeX commands destroyed by Python or shell escape handling — `\ref` eaten into a carriage return, and the "healed" form left behind after a text-mode round trip. |
| `audit_attribution.py` | Credit, in both directions: that every upstream project in the platform's `ATTRIBUTION.md` is cited, and that nothing listed there as an original contribution is handed to an upstream project. Needs `GNNARRATE_PLATFORM`. |
| `check_manuscript.py` | Citations resolve, refs have labels, environments and braces balance, no placeholders reach the PDF. |
| `check_jbhi.py` | JBHI submission rules: abstract word limit, document class, ORCIDs, page estimate, overlength charges. |
| `check_no_ai_mention.py` | Which AI mentions would print, separating models named as objects of study from anything else. |
| `check_tikz.py` | The TikZ figure statically, since there is no LaTeX toolchain here to compile it. |
| `section_sizes.py` | Word count per section, for deciding where to compress. |
| `wordcount.py` | Body word count against the page limit. |

## Before submitting

```bash
python paper_audit/audit_numbers.py     # expect: no discrepancies
python paper_audit/audit_coverage.py    # expect: UNACCOUNTED 0
python paper_audit/check_manuscript.py  # expect: no blocking problems
python paper_audit/check_jbhi.py        # expect: abstract within limit
python paper_audit/audit_prose.py       # expect: 0 problems
python paper_audit/audit_escapes.py     # expect: 0 problems
python paper_audit/audit_attribution.py # expect: 0 problems (needs the platform)
python examples/audit_artefacts.py      # expect: no integrity problems
```

`audit_artefacts.py` lives with the other examples because it checks generated
data rather than the manuscript: empty or truncated narratives, unparseable logs,
incomplete corpora, and derived files older than the narratives they summarise.
