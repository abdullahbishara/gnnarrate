"""Build a self-contained, blind annotation page from the exported claims.

The annotator must not see the automatic label, or agreement is circular -- they
would be confirming what the knowledge base already said rather than judging the
claim independently. This script therefore strips `auto_label` and `ot_score` from
what the page shows, and writes them to a separate answer key used only at scoring
time.

Claims are interleaved by automatic label so that any prefix of the sequence is
roughly balanced: stopping early still yields a usable, non-degenerate sample.

    python examples/make_annotation_task.py --annotator abdullah
    python examples/make_annotation_task.py --annotator alfarraj

Open the generated .html in a browser, judge each claim, then click Download and
save the JSON next to the page. Score with examples/score_annotation.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Claim validation &mdash; {annotator}</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 780px; margin: 2rem auto;
        padding: 0 1rem; }}
 .bar {{ height: 6px; background: #8883; border-radius: 3px; overflow: hidden; }}
 .bar > i {{ display: block; height: 100%; background: #4a9; width: 0; transition: .2s; }}
 .meta {{ display: flex; justify-content: space-between; font-size: .85rem;
          opacity: .7; margin: .5rem 0 1.5rem; }}
 .card {{ border: 1px solid #8884; border-radius: 10px; padding: 1.25rem 1.5rem;
          margin-bottom: 1.25rem; }}
 .look {{ display: flex; gap: .5rem; flex-wrap: wrap; margin-top: 1rem;
          padding-top: 1rem; border-top: 1px dashed #8884; }}
 .look a {{ font-size: .85rem; padding: .35rem .7rem; border: 1px solid #8886;
            border-radius: 6px; text-decoration: none; }}
 .look a:hover {{ background: #8882; }}
 .gene {{ font-weight: 700; font-size: 1.15rem; letter-spacing: .02em; }}
 .q {{ margin: .75rem 0 0; }}
 blockquote {{ margin: 1rem 0 0; padding-left: 1rem; border-left: 3px solid #8886;
               font-style: italic; opacity: .92; }}
 mark {{ background: #fd35; padding: 0 .15em; border-radius: 2px; }}
 .btns {{ display: flex; gap: .6rem; flex-wrap: wrap; }}
 button {{ font: inherit; padding: .6rem 1.1rem; border-radius: 8px;
           border: 1px solid #8886; background: #8881; cursor: pointer; }}
 button:hover {{ background: #8883; }}
 kbd {{ font: .8em monospace; border: 1px solid #8886; border-radius: 4px;
        padding: 0 .35em; opacity: .8; }}
 .done {{ text-align: center; padding: 3rem 1rem; }}
 .sec {{ font-size: .85rem; opacity: .7; margin-top: 2rem; }}
</style></head><body>
<h2>Gene&ndash;disease claim validation</h2>
<p class="sec">Annotator: <b>{annotator}</b> &middot; disease: <b>{disease}</b></p>
<div class="bar"><i id="prog"></i></div>
<div class="meta"><span id="count"></span><span id="saved"></span></div>
<div id="app"></div>
<p class="sec">
 <b>Protocol.</b> For each gene, follow the PubMed link and scan the titles. Judge
 <i>Evidence found</i> if there is published work reporting a role for this gene in
 this cancer (or a directly relevant pathway); <i>No clear evidence</i> if the search
 returns nothing relevant; <i>Unsure</i> if it is genuinely ambiguous. Spend about a
 minute per claim &mdash; a quick, consistent judgement is more useful than a slow,
 variable one. Judge independently: do not confer with the other annotator.
</p>
<p class="sec">
 Press <kbd>4</kbd> if the sentence is not actually asserting a link between
 <i>this gene</i> and the disease &mdash; for example if the gene is only named in
 passing, or the sentence explicitly denies a link. That tells us our automatic
 extractor mis-read the sentence, which we measure separately.
</p>
<p class="sec">
 <kbd>1</kbd> evidence found &nbsp; <kbd>2</kbd> no clear evidence &nbsp;
 <kbd>3</kbd> unsure &nbsp; <kbd>4</kbd> not a claim &nbsp; <kbd>&larr;</kbd> back<br>
 Progress saves automatically in this browser. Click <b>Download</b> when finished
 (or to hand over partway).
</p>
<script>
const CLAIMS = {claims};
const ANNOTATOR = {annotator_json};
const KEY = "gnnarrate-annot-" + ANNOTATOR;
let answers = JSON.parse(localStorage.getItem(KEY) || "{{}}");
let i = CLAIMS.findIndex(c => !(c.id in answers));
if (i < 0) i = CLAIMS.length;

function esc(s) {{ return s.replace(/[&<>]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;"}})[c]); }}

function render() {{
  const app = document.getElementById("app");
  const n = CLAIMS.length, done = Object.keys(answers).length;
  document.getElementById("prog").style.width = (100 * done / n) + "%";
  document.getElementById("count").textContent = done + " / " + n + " judged";
  document.getElementById("saved").textContent = done ? "saved locally" : "";

  if (i >= n) {{
    app.innerHTML = '<div class="card done"><p><b>All ' + n + ' claims judged.</b></p>' +
      '<p>Download your file and send it on.</p>' +
      '<div class="btns" style="justify-content:center">' +
      '<button onclick="dl()">Download my answers</button>' +
      '<button onclick="back()">Review last</button></div></div>';
    return;
  }}
  const c = CLAIMS[i];
  const sent = esc(c.sentence).replace(new RegExp("\\\\b" + c.gene + "\\\\b", "g"),
                                       "<mark>" + c.gene + "</mark>");
  const pm = "https://pubmed.ncbi.nlm.nih.gov/?term=" +
             encodeURIComponent(c.gene + ' AND ({disease_query})');
  const gc = "https://www.genecards.org/cgi-bin/carddisp.pl?gene=" +
             encodeURIComponent(c.gene);
  app.innerHTML =
    '<div class="card"><div class="gene">' + c.gene + '</div>' +
    '<p class="q">Is there <b>published evidence</b> linking <b>' + c.gene +
    '</b> to <b>' + {disease_json} + '</b>?</p>' +
    '<blockquote>&hellip;' + sent + '&hellip;</blockquote>' +
    '<div class="look"><span style="font-size:.85rem;opacity:.7;align-self:center">' +
    'Check:</span>' +
    '<a href="' + pm + '" target="_blank" rel="noopener">PubMed &nearr;</a>' +
    '<a href="' + gc + '" target="_blank" rel="noopener">GeneCards &nearr;</a></div>' +
    '</div>' +
    '<div class="btns">' +
    '<button onclick="ans(\\'supported\\')">1 &mdash; Evidence found</button>' +
    '<button onclick="ans(\\'unsupported\\')">2 &mdash; No clear evidence</button>' +
    '<button onclick="ans(\\'unsure\\')">3 &mdash; Unsure</button>' +
    '<button onclick="ans(\\'misextracted\\')" style="opacity:.75">' +
    '4 &mdash; Not a claim about this gene</button>' +
    '<button onclick="back()" style="margin-left:auto">&larr; Back</button></div>';
}}
function ans(v) {{
  answers[CLAIMS[i].id] = v;
  localStorage.setItem(KEY, JSON.stringify(answers));
  i++; render();
}}
function back() {{ if (i > 0) {{ i--; render(); }} }}
function dl() {{
  const blob = new Blob([JSON.stringify(
      {{annotator: ANNOTATOR, answers: answers}}, null, 1)], {{type: "application/json"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "annotations_" + ANNOTATOR + ".json";
  a.click();
}}
addEventListener("keydown", e => {{
  if (i >= CLAIMS.length) return;
  if (e.key === "1") ans("supported");
  else if (e.key === "2") ans("unsupported");
  else if (e.key === "3") ans("unsure");
  else if (e.key === "4") ans("misextracted");
  else if (e.key === "ArrowLeft") back();
}});
render();
</script></body></html>
"""


def interleave(rows: list[dict]) -> list[dict]:
    """Alternate auto-supported and auto-unsupported so any prefix stays balanced."""
    sup = [r for r in rows if r["auto_label"] == "supported"]
    uns = [r for r in rows if r["auto_label"] != "supported"]
    out = []
    for a, b in zip(sup, uns):
        out += [a, b]
    out += sup[len(uns):] + uns[len(sup):]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--claims", default="data/results_kirc/claims_for_expert.csv")
    ap.add_argument("--annotator", required=True, help="short name, e.g. abdullah")
    ap.add_argument("--disease", default="clear cell renal carcinoma")
    ap.add_argument("--disease-query", default="renal cell carcinoma OR kidney cancer",
                    help="PubMed query fragment for the disease")
    ap.add_argument("--outdir", default="data/annotation")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.claims, newline="", encoding="utf-8")))
    for n, r in enumerate(rows):
        r["id"] = f"{r['item_id']}::{r['gene']}::{n}"
    rows = interleave(rows)

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # Answer key (auto labels) -- never shown to the annotator.
    key = {r["id"]: {"auto_label": r["auto_label"], "gene": r["gene"],
                     "ot_score": r["ot_score"], "item_id": r["item_id"]} for r in rows}
    (out / "answer_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")

    # Blind payload.
    blind = [{"id": r["id"], "gene": r["gene"], "sentence": r["sentence"]} for r in rows]
    page = TEMPLATE.format(
        annotator=args.annotator,
        annotator_json=json.dumps(args.annotator),
        disease=args.disease,
        disease_json=json.dumps(args.disease),
        disease_query=args.disease_query,
        claims=json.dumps(blind),
    )
    path = out / f"annotate_{args.annotator}.html"
    path.write_text(page, encoding="utf-8")

    n_sup = sum(1 for r in rows if r["auto_label"] == "supported")
    print(f"wrote {path}")
    print(f"  {len(rows)} claims ({n_sup} auto-supported, {len(rows)-n_sup} auto-unsupported)")
    print(f"  answer key -> {out/'answer_key.json'} (not visible to the annotator)")
    print(f"\nOpen the .html in a browser. Keys: 1 supported, 2 not supported, 3 unsure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
