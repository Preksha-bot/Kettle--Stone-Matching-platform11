"""Builds the three risk PDFs from the content below.

    python risk-docs/build.py

Writes 1-four-risks.pdf, 2-assumptions.pdf and 3-risks-and-assumptions.pdf
next to this file. Uses Microsoft Edge (headless) to print HTML to PDF.
"""
import html
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
DATE = "October 30, 2026"

# ---------------------------------------------------------------- content

RISKS = [
    {
        "name": "Value",
        "question": "Will it fill more openings?",
        "hours": "6 of 20 hours",
        "plan": [
            ("Belief", "a correct list of 3 names fills more openings, even with overnight cancels."),
            ("Check", "how many of the 44 openings a perfect list could fill, vs. the 12 filled."),
            ("Ask", "which openings could Tanya act on, and at what time of day?"),
            ("Limit", "only 4 weeks of data, and no December."),
        ],
        "change": "The plan bet that the list would help despite overnight cancels. "
                  "The data says the names were mostly there; the time to use them was not.",
        "now": [
            ("The right people were there.", "A fit for 34 of the 44 openings."),
            ("Few were filled.", "12 of 44 (27%) vs. a 70% target; about $920 a week lost."),
            ("Timing is the real gap.", "31 of 36 late cancels arrive before Tanya is free at 10:30."),
            ("Very short notice fails.", "3 had under 2 hours; none was filled."),
            ("Names must come when the desk can act.", "The inbox and call list show them at once."),
            ("Still unproven.", "No past offer results exist; the new report will count refills."),
        ],
        "assumptions": [7],
    },
    {
        "name": "Feasibility",
        "question": "Can we build it so every name is right?",
        "hours": "5 of 20 hours",
        "plan": [
            ("Belief", "simple rules can read the shorthand, repeat lines and dead lines."),
            ("Belief", "the same rules will work on Friday\u2019s new files."),
            ("Check", "the messy parts first, against Tanya\u2019s stale and duplicate marks."),
            ("Check", "all 44 picks against Tanya\u2019s, plus my own new-shorthand lines."),
        ],
        "change": "Rules were enough to read the notebook, so we chose a script over AI. "
                  "The hard part moved from reading notes to getting live data from Kneadly.",
        "now": [
            ("The matcher works on the sample.", "44 of 44 openings, 0 wrong names."),
            ("A script, not AI.", "Same answer every run; unclear lines are held, never guessed."),
            ("The platform runs locally.", "Board, inbox, offers and report, with the same matcher inside."),
            ("Kneadly is the big unknown.", "No answer yet on an API, cancel alerts or holds."),
            ("Booking history is fragile.", "A 2-day file gave wrong names on 35 of 44 openings."),
            ("Overfitting is possible.", "Tuned on 44 openings; new weeks are the real test."),
        ],
        "assumptions": [1, 2],
    },
    {
        "name": "Usability",
        "question": "Can a busy desk use it in the time it has?",
        "hours": "4 of 20 hours",
        "plan": [
            ("Belief", "anyone can read one opening and know who to call, and why, in 10 seconds."),
            ("Check", "the order of names can be explained."),
            ("Ask", "can Tanya or a stand-in try a sample output?"),
            ("Ask", "how do Jos\u00e9e, Kelsey and Dave want their say?"),
        ],
        "change": "Reading the output was the easy part. The real bar is Tanya\u2019s time: "
                  "about 30 seconds between people, and \u201cless time than the book, not more.\u201d",
        "now": [
            ("Output reads at a glance.", "Up to 3 names, each with phone and a one-line reason."),
            ("Order is explainable, not decided.", "Default is first asked; Marc and Tanya choose."),
            ("Therapists\u2019 say is partly known.", "Jos\u00e9e sees who first; Amira and Rachel unknown."),
            ("A board replaces the notebook.", "Editable cards, no free text. Built Oct 30."),
            ("Not yet tried by Tanya.", "Her timing test decides if the book is retired."),
            ("Kneadly has no hold.", "The desk must block each slot by hand before offering."),
        ],
        "assumptions": [3, 4],
    },
    {
        "name": "Viability",
        "question": "Does it fit the clinic\u2019s budget, privacy rules and time?",
        "hours": "5 of 20 hours",
        "plan": [
            ("Belief", "it runs under $50 a month, with no health details leaving the desk."),
            ("Belief", "Julie keeps it running in about an hour a month."),
            ("Check", "every field that leaves the computer, any AI service, the real cost."),
            ("Ask", "where does Kneadly store data, and is the $45 plan needed?"),
        ],
        "change": "A local script removed today\u2019s cost and privacy questions. "
                  "Both come back once the platform connects to Kneadly.",
        "now": [
            ("Today it costs $0.", "No internet, AI service or subscription."),
            ("No health details leave the desk.", "Tests check every output file."),
            ("Julie: about 1 hour a month.", "The platform needs more care than the script."),
            ("Live Kneadly may cost ~$45 a month.", "Unchecked; just under Marc\u2019s $50."),
            ("Hosting would break the budget.", "Another $5\u201312 a month, so it stays local."),
            ("Marc signs off first.", "A one-page note before client data goes anywhere new."),
        ],
        "assumptions": [5, 6],
    },
]

ASSUMPTIONS = {
    1: {
        "area": "Matching",
        "title": "The matching rules stay right on live data.",
        "risky": "Tuned on 44 openings and 60 lines; a gap in booking history gave 35 of 44 wrong.",
        "wrong": "Someone unsuitable, or already booked, gets a call.",
        "check": "Friday\u2019s new openings, then every real week added as a test.",
    },
    2: {
        "area": "Platform \u00b7 Kneadly",
        "title": "Kneadly can send us live booking data.",
        "risky": "Nobody knows if it has an API or cancel alerts; Julie hasn\u2019t answered.",
        "wrong": "The platform stays on file uploads and desk taps.",
        "check": "Julie confirms the API, its fields and the plan it needs.",
    },
    3: {
        "area": "Platform \u00b7 bookings",
        "title": "The desk blocks each slot before offering it.",
        "risky": "Kneadly has no hold, so a busy desk must block the time by hand.",
        "wrong": "The slot goes online while offered: a double booking, Marc\u2019s first deal-breaker.",
        "check": "Tanya tries it on real openings; the daily check flags any miss.",
    },
    4: {
        "area": "Platform \u00b7 adoption",
        "title": "Tanya will use the board instead of the notebook.",
        "risky": "She has about 30 seconds between people; it must beat the book on time.",
        "wrong": "Two lists drift apart and the platform falls out of use.",
        "check": "Tanya\u2019s 15-minute timing test, then one cut-over date for everyone.",
    },
    5: {
        "area": "Information security",
        "title": "Health details never leave the desk computer.",
        "risky": "Hosting, an AI helper or text-reading would each send data out.",
        "wrong": "Client health data sits with an outside service Marc never approved.",
        "check": "Marc signs a one-page note first; tests scan every output.",
    },
    6: {
        "area": "Cost",
        "title": "It stays under $50 a month and about 1 hour of Julie\u2019s time.",
        "risky": "The ~$45 Kneadly plan is unchecked; a web app needs more care than a script.",
        "wrong": "Marc says no: \u201cA hundred and fifty, no\u201d and \u201cJulie can\u2019t babysit it.\u201d",
        "check": "Julie checks the real price before connecting; log her hours for a month.",
    },
    7: {
        "area": "Outcome",
        "title": "Names ready the moment a cancel is heard will fill more openings.",
        "risky": "Most cancels land before 10:30, and no past offer results exist to prove it.",
        "wrong": "The platform adds work without lifting refills above 27%.",
        "check": "The report\u2019s refill rate over the first month, vs. 27% today.",
    },
}

# ---------------------------------------------------------------- layout

CSS = """
@page { size: Letter; margin: 0.95in 1.05in; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Calibri, Carlito, Arial, sans-serif; font-size: 11.5pt; line-height: 1.45;
       color: #1f2328; margin: 0; background: #fff; }
.page { break-after: page; }
.page:last-child { break-after: auto; }
.doc-title { font-size: 11pt; color: #5b6570; margin: 0 0 26pt; padding-bottom: 8pt;
             border-bottom: 1px solid #d9dee3; }
.doc-title b { color: #1f2328; font-size: 13pt; }
h1 { font-size: 24pt; line-height: 1.1; margin: 0; color: #12403f; font-weight: 700; }
.question { font-size: 13pt; color: #5b6570; margin: 4pt 0 0; }
h2 { font-size: 9.5pt; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
     color: #2e7d7a; margin: 24pt 0 8pt; }
h2 span { color: #8a949e; font-weight: 400; letter-spacing: 0.04em; }
ul { list-style: none; margin: 0; padding: 0; }
li { position: relative; padding-left: 14pt; margin: 0 0 6pt; }
li::before { content: ""; position: absolute; left: 2pt; top: 0.62em; width: 4.5pt; height: 4.5pt;
             border-radius: 50%; background: #2e7d7a; }
.plan li::before { background: #b7c0c8; }
.label { color: #5b6570; font-weight: 700; }
.change { margin: 0; padding: 2pt 0 2pt 12pt; border-left: 3px solid #a8d3d0; color: #3a434c;
          font-style: italic; }
.assumption { margin: 0 0 14pt; break-inside: avoid; }
.assumption:last-child { margin-bottom: 0; }
.a-head { margin: 0 0 4pt; }
.a-num { display: inline-block; min-width: 24pt; color: #2e7d7a; font-weight: 700; }
.a-title { font-weight: 700; }
.a-area { display: inline-block; margin-left: 6pt; padding: 0 6pt; font-size: 8.5pt; line-height: 1.6;
          border-radius: 3pt; background: #eef2f4; color: #5b6570; vertical-align: 1pt; }
.a-rows { display: grid; grid-template-columns: 62pt 1fr; column-gap: 6pt; row-gap: 2pt;
          margin-left: 24pt; font-size: 10.5pt; }
.a-rows .k { color: #8a949e; }
.intro { margin: 0 0 24pt; color: #3a434c; }
.big .assumption { margin-bottom: 22pt; }
.big .a-rows { font-size: 11pt; row-gap: 3pt; }
"""


def e(text):
    return html.escape(text, quote=False)


def page(body):
    return f'<section class="page">{body}</section>'


def doc_title(title):
    return f'<p class="doc-title"><b>{e(title)}</b> &nbsp;\u00b7&nbsp; Kettle &amp; Stone &nbsp;\u00b7&nbsp; {DATE}</p>'


def plan_block(risk):
    items = "".join(f'<li><span class="label">{e(k)}:</span> {e(v)}</li>' for k, v in risk["plan"])
    return (f'<h2>In plan.md <span>\u00b7 Oct 26 \u00b7 {e(risk["hours"])}</span></h2>'
            f'<ul class="plan">{items}</ul>'
            f'<h2>What changed</h2><p class="change">{e(risk["change"])}</p>')


def now_block(risk):
    items = "".join(f"<li><b>{e(k)}</b> {e(v)}</li>" for k, v in risk["now"])
    return f'<h2>Now <span>\u00b7 Oct 30</span></h2><ul class="now">{items}</ul>'


def assumption_block(n):
    a = ASSUMPTIONS[n]
    rows = "".join(f'<span class="k">{k}</span><span>{e(a[f])}</span>'
                   for k, f in (("Why risky", "risky"), ("If wrong", "wrong"), ("Check", "check")))
    return (f'<div class="assumption"><p class="a-head"><span class="a-num">A{n}</span>'
            f'<span class="a-title">{e(a["title"])}</span><span class="a-area">{e(a["area"])}</span></p>'
            f'<div class="a-rows">{rows}</div></div>')


def risk_page(i, risk, first_title=None, with_assumptions=False):
    head = doc_title(first_title) if first_title and i == 0 else ""
    body = (head + f'<h1>{i + 1}. {e(risk["name"])}</h1><p class="question">{e(risk["question"])}</p>'
            + plan_block(risk) + now_block(risk))
    if with_assumptions:
        body += "<h2>Assumptions behind it</h2>" + "".join(assumption_block(n) for n in risk["assumptions"])
    return page(body)


def html_doc(title, pages):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)}</title>'
            f"<style>{CSS}</style></head><body>{''.join(pages)}</body></html>")


def doc_risks():
    t = "The four risks: plan vs. now"
    return t, [risk_page(i, r, t) for i, r in enumerate(RISKS)]


def doc_assumptions():
    t = "Key assumptions"
    intro = ('<p class="intro">The seven assumptions the platform rests on. Each is unproven, '
             'and each would change the plan if it turned out wrong.</p>')
    first = doc_title(t) + "<h1>Key assumptions</h1>" + intro + "".join(assumption_block(n) for n in (1, 2, 3, 4))
    second = "".join(assumption_block(n) for n in (5, 6, 7))
    return t, [page(f'<div class="big">{first}</div>'), page(f'<div class="big">{second}</div>')]


def doc_combined():
    t = "Risks and assumptions"
    return t, [risk_page(i, r, t, with_assumptions=True) for i, r in enumerate(RISKS)]


def print_pdf(html_text, out_pdf, tmp):
    # Edge prints into the temp folder; the PDF is then copied next to this file.
    src = Path(tmp) / (out_pdf.stem + ".html")
    printed = Path(tmp) / out_pdf.name
    src.write_text(html_text, encoding="utf-8")
    subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-pdf-header-footer", f"--user-data-dir={Path(tmp) / 'edge'}",
                    f"--print-to-pdf={printed}", src.as_uri()], check=True)
    # Edge can exit before the PDF lands, so wait until the file stops growing.
    size = -1
    for _ in range(120):
        time.sleep(0.5)
        if printed.exists() and printed.stat().st_size == size > 0:
            break
        size = printed.stat().st_size if printed.exists() else -1
    else:
        raise SystemExit(f"Edge did not write {printed}")
    shutil.copyfile(printed, out_pdf)


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for name, build in (("1-four-risks", doc_risks),
                            ("2-assumptions", doc_assumptions),
                            ("3-risks-and-assumptions", doc_combined)):
            title, pages = build()
            out = HERE / f"{name}.pdf"
            print_pdf(html_doc(title, pages), out, tmp)
            print("wrote", out)


if __name__ == "__main__":
    main()
