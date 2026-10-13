#!/usr/bin/env python3
"""
build_deck.py — assemble the 21 rendered slides into the final presentable deck
(ISI-5794). Produces two portable, directly-usable artifacts:

  dist/PAC-there-is-no-spoon.pptx   editable 16:9 deck — one full-bleed slide PNG
                                    per slide + A's Part-3 timed narrative as
                                    PowerPoint speaker notes. Opens / imports into
                                    PowerPoint · Keynote · Google Slides.
  dist/PAC-there-is-no-spoon.pdf    universal, click-to-present PDF (one slide/page).

v1 (ISI-4048) shipped as a markdown slide *spec* (presentation/slides-draft.md), not a
binary deck, so there is no prior PPTX/Slides file to byte-mirror; this matches the
design-system's stated export path (2560x1440 PNGs → slide tool) and adds an editable
PPTX + a universal PDF so Henrik can present or hand-edit directly.

Speaker notes are parsed live from narrative-and-slide-copy.md Part 3 (single source of
truth — no copy drift).
"""
import os, re, glob
from PIL import Image

HERE = os.path.dirname(__file__)
IMG = os.path.join(HERE, "images")
DIST = os.path.join(HERE, "dist")
NARR = os.path.join(HERE, "narrative-and-slide-copy.md")
os.makedirs(DIST, exist_ok=True)

# ----------------------------------------------------------- slide file ordering
# explicit 1..21 order (filenames are not strictly sortable past the number)
SLIDES = {
    1: "slide-01-title.png", 2: "slide-02-bluepill.png", 3: "slide-03-basics.png",
    4: "slide-04-discussion.png", 5: "slide-05-otel.png", 6: "slide-06-sampling.png",
    7: "slide-07-rum.png", 8: "slide-08-dual.png", 9: "slide-09-dql.png",
    10: "slide-10-discussion.png", 11: "slide-11-skill.png", 12: "slide-12-engine.png",
    13: "slide-13-architecture.png", 14: "slide-14-worlds.png", 15: "slide-15-demo.png",
    16: "slide-16-demo-wall.png", 17: "slide-17-demo-render.png", 18: "slide-18-demo-diff.png",
    19: "slide-19-loop.png", 20: "slide-20-limits.png", 21: "slide-21-close.png",
}

# ----------------------------------------------------------- speaker notes parse
def parse_notes():
    """Return {slide_num: narrative_text} parsed from Part 3 of the copy doc."""
    notes = {}
    if not os.path.exists(NARR):
        return notes
    txt = open(NARR, encoding="utf-8").read()
    # isolate Part 3
    m = re.search(r"# Part 3 —.*?(?=\n# Part 4)", txt, re.S)
    body = m.group(0) if m else txt
    # split into heading blocks
    blocks = re.split(r"\n### ", body)
    for b in blocks:
        head = b.split("\n", 1)[0]
        rest = b.split("\n", 1)[1] if "\n" in b else ""
        mm = re.search(r"Slides?\s+(\d+)\s*[–-]\s*(\d+)", head)
        single = re.search(r"Slide\s+(\d+)", head)
        if "note" in head.lower() and single and not mm:
            continue  # skip the "Slide 10 note — see below" stub
        # clean body: strip stage directions kept, collapse whitespace
        content = rest.strip()
        content = re.sub(r"\n{2,}", "\n\n", content)
        label = "### " + head  # keep the timed heading for the presenter
        full = label.replace("### ", "").strip() + "\n\n" + content
        if mm:
            a, c = int(mm.group(1)), int(mm.group(2))
            for n in range(a, c + 1):
                notes[n] = full
        elif single:
            n = int(single.group(1))
            notes.setdefault(n, full)
    return notes

# ----------------------------------------------------------- PDF
def build_pdf():
    imgs = [Image.open(os.path.join(IMG, SLIDES[n])).convert("RGB") for n in range(1, 22)]
    out = os.path.join(DIST, "PAC-there-is-no-spoon.pdf")
    imgs[0].save(out, "PDF", save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"  wrote {os.path.relpath(out, HERE)}  ({len(imgs)} pages)")

# ----------------------------------------------------------- PPTX
def build_pptx(notes):
    from pptx import Presentation
    from pptx.util import Inches, Emu
    prs = Presentation()
    prs.slide_width = Inches(13.333)   # 16:9
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    for n in range(1, 22):
        slide = prs.slides.add_slide(blank)
        path = os.path.join(IMG, SLIDES[n])
        slide.shapes.add_picture(path, 0, 0, width=prs.slide_width, height=prs.slide_height)
        note = notes.get(n, "")
        if note:
            slide.notes_slide.notes_text_frame.text = note
    out = os.path.join(DIST, "PAC-there-is-no-spoon.pptx")
    prs.save(out)
    print(f"  wrote {os.path.relpath(out, HERE)}  (21 slides, notes on {sum(1 for n in range(1,22) if notes.get(n))})")

if __name__ == "__main__":
    missing = [SLIDES[n] for n in range(1, 22) if not os.path.exists(os.path.join(IMG, SLIDES[n]))]
    if missing:
        raise SystemExit(f"missing slide renders: {missing}\nrun: python3 gen_deck.py")
    print("assembling deck -> dist/")
    notes = parse_notes()
    build_pdf()
    build_pptx(notes)
    print("done.")
