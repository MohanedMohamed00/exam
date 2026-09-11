# -*- coding: utf-8 -*-
"""Extract all MCQs with answers into questions.js / questions.json"""
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(
    r"c:\Users\mohan\AppData\Roaming\Cursor\User\workspaceStorage\c552410bb94c760fdefca38162665e11\pdfs"
)
OUT = Path(r"c:\Users\mohan\OneDrive\Desktop\New folder")

PDFS = {
    "exam1": BASE / r"a012bd68-db34-4291-8774-8b4e28d9c6fa\Exam1.pdf",
    "exam2": BASE / r"b378f9fe-a5b9-498d-ac94-2c7f700e4f6c\exam 2.pdf",
    "exam3": BASE / r"2e479316-caf0-4c0f-a1a8-b292526cebb6\exam 3.pdf",
    "max": BASE / r"e9ae63d3-9327-419c-8468-267f83b21c92\max.pdf",
}

WATERMARK = re.compile(
    r"^(EL3OMDA|Page|EX\d+|VOCABULARY|EXPRESSIONS|EXAM|BANK|QUESTIONS|ENGLISH)$",
    re.I,
)
ENG_TOKEN = re.compile(r"[A-Za-z][A-Za-z'/\-]*(?:\s*/\s*[A-Za-z][A-Za-z'/\-]*)*")


BLANK = "……"


def clean(text: str) -> str:
    text = text.replace("\x03", " ").replace("\xa0", " ")
    text = text.replace("…", "...")
    text = re.sub(r"\.{3,}", " <<BLANK>> ", text)
    text = re.sub(r"[^\x20-\x7E]+", " ", text)
    text = text.replace("<<BLANK>>", BLANK)
    text = re.sub(r"\s+", " ", text).strip(" ,;:")
    return text


def english_only(text: str) -> str:
    text = clean(text)
    parts = ENG_TOKEN.findall(text)
    # drop phone-like / watermark crumbs
    parts = [p for p in parts if not re.fullmatch(r"\d+", p) and "EL3OMDA" not in p.upper()]
    return clean(" ".join(parts))


def is_green_fill(fill) -> bool:
    if not fill or len(fill) < 3:
        return False
    r, g, b = fill[:3]
    return g > 0.55 and r < 0.65 and b < 0.65 and (g - r) > 0.15 and (g - b) > 0.15


def latin_words(page):
    words = []
    for w in page.get_text("words"):
        t = w[4]
        if re.search(r"[A-Za-z]", t) or re.fullmatch(r"\.+", t):
            words.append(w)
    return words


def build_stems(words, min_len=18):
    buckets = {}
    for w in words:
        if WATERMARK.match(w[4]):
            continue
        key = round(w[1], 0)
        buckets.setdefault(key, []).append(w)
    stems = []
    for y, ws in sorted(buckets.items()):
        ws = sorted(ws, key=lambda x: x[0])
        texts = [w[4] for w in ws]
        joined = " ".join(texts)
        cj = clean(joined)
        # Only lowercase a/b/c/d option rows — never treat "A balanced..." as an option
        if re.match(r"^[abcd](?:\.|\s)\s*\S+", cj) and len(cj) < 60:
            continue
        has_blank = any(re.fullmatch(r"\.+", w[4]) for w in ws) or BLANK in cj or "……" in cj
        has_sentence = len(cj) >= min_len and re.search(r"[A-Za-z]{3,}", cj)
        has_cont = (
            len(cj) >= 8
            and cj[:1].islower()
            and ws[0][0] < 160
            and re.search(r"[A-Za-z]{3,}", cj)
            and not re.match(r"^[abcd](?:\.|\s)", cj)
        )
        if has_blank or has_cont or (has_sentence and ws[0][0] < 120 and cj[:1].isupper()):
            if any(
                h in cj
                for h in ("VOCABULARY", "ENGLISH QUESTIONS", "Page ", "EL3OMDA", "VERSION", "BANK")
            ):
                continue
            if re.match(r"^\d+\s*$", cj):
                continue
            stems.append({"y": y, "text": cj, "x0": ws[0][0]})
    merged = []
    for s in stems:
        txt = s["text"]
        if not re.search(r"[A-Za-z]{3,}", txt) and "……" not in txt:
            continue
        if merged and s["y"] - merged[-1]["y"] <= 42:
            prev = merged[-1]["text"]
            if (
                (not re.search(r"[.?!]$", prev) and len(txt) < 100)
                or txt[0].islower()
                or (txt.startswith("……") and not prev.endswith("……"))
                or (prev.endswith(("means", "be", "is", "are", "the", "a", "an", "of", "to", "for", "information")) and len(txt) < 80)
            ):
                merged[-1]["text"] = clean(prev + " " + txt)
                continue
        merged.append(dict(s))
    return merged


def make_q(key, source, qnum, question, by, correct_letter):
    return {
        "sourceKey": key,
        "source": source,
        "qnum": qnum,
        "question": question,
        "choices": [by[L]["text"] for L in "abcd"],
        "answer": ord(correct_letter) - ord("a"),
    }


def nearest_stem(stems, cy, lo=5, hi=220):
    cands = [
        s
        for s in stems
        if cy - hi < s["y"] < cy - lo and re.search(r"[A-Za-z]{4,}", s["text"])
    ]
    if not cands:
        return None
    cands.sort(key=lambda s: s["y"])
    best = cands[-1]
    # Avoid tiny/orphan fragments like "will ……" when a fuller stem sits just above
    if len(best["text"]) < 28 or re.match(r"^……", best["text"]):
        fuller = [s for s in cands if len(s["text"]) >= 28 and not re.match(r"^……", s["text"])]
        if fuller:
            best = fuller[-1]
    return best


def is_option_dash(text: str) -> bool:
    return bool(re.fullmatch(r"[-–—_.]{3,}", clean(text).replace(" ", "")))


# ---------- EXAM 1: green highlight boxes (219) ----------
def extract_exam1():
    doc = pymupdf.open(PDFS["exam1"])
    out = []
    for page in doc:
        words = page.get_text("words")
        eng = latin_words(page)
        greens = [
            pymupdf.Rect(d["rect"])
            for d in page.get_drawings()
            if is_green_fill(d.get("fill"))
        ]
        stems = build_stems(eng)

        opts = []
        for w in words:
            if w[4].lower() not in "abcd" or len(w[4]) != 1:
                continue
            letter = w[4].lower()
            ymid = (w[1] + w[3]) / 2
            # Collect ALL latin tokens to the right on same row (no early break)
            cands = []
            for w2 in eng:
                if w2[0] <= w[0] + 4:
                    continue
                if w2[0] > w[0] + 220:
                    continue
                if abs(((w2[1] + w2[3]) / 2) - ymid) > 7:
                    continue
                if w2[4].lower() in "abcd" and len(w2[4]) == 1:
                    continue
                if re.fullmatch(r"\.+", w2[4]):
                    continue
                if re.fullmatch(r"\d{6,}", w2[4]):
                    continue
                tok = english_only(w2[4])
                if tok:
                    cands.append((w2[0], tok))
            cands.sort(key=lambda x: x[0])
            phrase = clean(" ".join(t for _, t in cands))
            phrase = english_only(phrase)
            if not phrase:
                # fallback: span text next to letter
                for b in page.get_text("dict")["blocks"]:
                    if b.get("type") != 0:
                        continue
                    for line in b.get("lines", []):
                        for s in line.get("spans", []):
                            if abs(s["bbox"][1] - w[1]) > 4:
                                continue
                            if s["bbox"][0] < w[0] - 2:
                                continue
                            if s["bbox"][0] > w[0] + 220:
                                continue
                            phrase = english_only(s["text"])
                            if phrase:
                                break
                        if phrase:
                            break
                    if phrase:
                        break
            if not phrase:
                continue
            rect = pymupdf.Rect(w[0] - 4, w[1] - 6, min(w[0] + 260, page.rect.width), w[3] + 18)
            opts.append(
                {
                    "letter": letter,
                    "text": phrase,
                    "rect": rect,
                    "y": w[1],
                    "x": w[0],
                    "ymid": ymid,
                }
            )

        # Group into questions: a/b row then c/d row (~25-40pt apart)
        opts = sorted(opts, key=lambda o: (o["y"], o["x"]))
        used = set()
        groups = []
        for i, o in enumerate(opts):
            if i in used or o["letter"] != "a":
                continue
            # find siblings within y window
            window = [o]
            for j, o2 in enumerate(opts):
                if j == i or j in used:
                    continue
                if 0 <= o2["y"] - o["y"] <= 45:
                    window.append(o2)
            by = {}
            for o2 in sorted(window, key=lambda x: (x["y"], x["x"])):
                if o2["letter"] not in by:
                    by[o2["letter"]] = o2
            if set(by) == set("abcd"):
                for o2 in by.values():
                    # mark used by identity
                    for j, cand in enumerate(opts):
                        if j not in used and cand is o2:
                            used.add(j)
                groups.append(by)

        # Match each green to a group
        for g in greens:
            best = None
            best_score = 1e9
            for by in groups:
                for L, o in by.items():
                    # expand intersection tolerance
                    hit = g.intersects(o["rect"]) or (
                        abs(o["ymid"] - (g.y0 + g.y1) / 2) < 18
                        and o["x"] < g.x1
                        and o["x"] + 180 > g.x0
                    )
                    if not hit:
                        continue
                    score = abs(o["y"] - g.y0) + abs(o["x"] - g.x0)
                    if score < best_score:
                        best_score = score
                        best = (by, L)
            if not best:
                continue
            by, correct = best
            cy = min(by[L]["y"] for L in "abcd")
            stem = nearest_stem(stems, cy, lo=8, hi=200)
            if not stem:
                # fallback: rebuild line of English words just above options
                above = [
                    w
                    for w in eng
                    if cy - 160 < w[1] < cy - 8
                    and w[0] < 400
                    and re.search(r"[A-Za-z]{3,}", w[4])
                    and not WATERMARK.match(w[4])
                ]
                if not above:
                    continue
                buckets = {}
                for w in above:
                    buckets.setdefault(round(w[1], 0), []).append(w)
                yk = max(buckets)
                line = clean(
                    " ".join(w[4] for w in sorted(buckets[yk], key=lambda x: x[0]))
                )
                qtext = line if "……" in line or "..." in line else english_only(line)
                if len(qtext) < 12:
                    continue
            else:
                qtext = stem["text"]
            out.append(
                make_q(
                    "exam1",
                    "Exam 1 — Vocabulary & Expressions",
                    len(out) + 1,
                    qtext,
                    by,
                    correct,
                )
            )
    return out


# ---------- EXAM 2: colored option text ----------
def extract_exam2():
    CORRECT_COLOR = 1332013
    doc = pymupdf.open(PDFS["exam2"])
    out = []
    for page in doc:
        words = latin_words(page)
        stems = build_stems(words)

        option_spans = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    t = clean(s["text"])
                    if not t or not re.search(r"[A-Za-z]", t):
                        continue
                    if re.match(r"^[abcd]\.?$", t, re.I):
                        continue
                    option_spans.append(
                        {
                            "text": t,
                            "y": s["bbox"][1],
                            "x": s["bbox"][0],
                            "correct": s["color"] == CORRECT_COLOR,
                        }
                    )

        opts = []
        for w in words:
            m = re.match(r"^([abcd])\.$", w[4], re.I)
            if not m:
                continue
            letter = m.group(1).lower()
            best = None
            for sp in option_spans:
                if sp["x"] <= w[0]:
                    continue
                if abs(sp["y"] - w[1]) > 10:
                    continue
                if sp["x"] > w[0] + 160:
                    continue
                if best is None or sp["x"] < best["x"]:
                    best = sp
            if not best:
                continue
            opts.append(
                {
                    "letter": letter,
                    "text": best["text"],
                    "y": w[1],
                    "x": w[0],
                    "correct": best["correct"],
                }
            )

        opts = sorted(opts, key=lambda o: (o["y"], o["x"]))
        clusters = []
        cur = []
        for o in opts:
            if not cur:
                cur = [o]
            elif o["y"] - cur[0]["y"] < 55:
                cur.append(o)
            else:
                clusters.append(cur)
                cur = [o]
        if cur:
            clusters.append(cur)

        for cl in clusters:
            by = {}
            for o in sorted(cl, key=lambda x: (x["y"], x["x"])):
                if o["letter"] not in by:
                    by[o["letter"]] = o
                elif o["correct"]:
                    by[o["letter"]] = o
            if set(by) != set("abcd"):
                continue
            correct = next((L for L in "abcd" if by[L].get("correct")), None)
            if not correct:
                continue
            cy = min(by[L]["y"] for L in "abcd")
            stem = nearest_stem(stems, cy, lo=5, hi=200)
            if not stem:
                continue
            out.append(
                make_q(
                    "exam2",
                    "Exam 2 — Vocabulary Mastery",
                    len(out) + 1,
                    stem["text"],
                    by,
                    correct,
                )
            )
    return out


# ---------- EXAM 3: colored word/letter + checkmark ----------
def extract_exam3():
    CORRECT_WORD = 417606
    CORRECT_LETTER = 1409085
    doc = pymupdf.open(PDFS["exam3"])
    out = []
    for page in doc:
        words = latin_words(page)
        stems = build_stems(words, min_len=12)

        letter_spans = []
        word_spans = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    t = s["text"].strip()
                    if not t:
                        continue
                    if t.lower() in "abcd" and len(t) == 1:
                        letter_spans.append(
                            {
                                "letter": t.lower(),
                                "y": s["bbox"][1],
                                "x": s["bbox"][0],
                                "correct": s["color"] == CORRECT_LETTER,
                            }
                        )
                    elif re.search(r"[A-Za-z]{2,}", t) and "✔" not in t and "✓" not in t:
                        ct = english_only(t) or clean(t)
                        if ct and not WATERMARK.match(ct):
                            word_spans.append(
                                {
                                    "text": ct,
                                    "y": s["bbox"][1],
                                    "x": s["bbox"][0],
                                    "correct": s["color"] == CORRECT_WORD,
                                }
                            )

        opts = []
        for ls in letter_spans:
            cands = [
                ws
                for ws in word_spans
                if ws["x"] > ls["x"]
                and abs(ws["y"] - ls["y"]) <= 10
                and ws["x"] <= ls["x"] + 220
            ]
            # Dashes / blank options (---------)
            if not cands:
                for w in page.get_text("words"):
                    if w[0] <= ls["x"] + 4 or w[0] > ls["x"] + 220:
                        continue
                    if abs(w[1] - ls["y"]) > 10:
                        continue
                    if is_option_dash(w[4]):
                        cands = [
                            {
                                "text": "---------",
                                "y": w[1],
                                "x": w[0],
                                "correct": False,
                            }
                        ]
                        break
            if not cands:
                continue
            best = min(cands, key=lambda ws: ws["x"])
            opts.append(
                {
                    "letter": ls["letter"],
                    "text": best["text"],
                    "y": ls["y"],
                    "x": ls["x"],
                    "correct": ls["correct"] or best.get("correct", False),
                }
            )

        # Prefer marker-first: start a cluster from each correct option
        opts = sorted(opts, key=lambda o: (o["y"], o["x"]))
        used = set()
        for i, o in enumerate(opts):
            if not o["correct"] or i in used:
                continue
            by = {}
            for win in (85, 100, 120, 150):
                window = [
                    o2
                    for j, o2 in enumerate(opts)
                    if abs(o2["y"] - o["y"]) < win and j not in used
                ]
                by = {}
                for o2 in sorted(window, key=lambda x: (x["y"], x["x"])):
                    if o2["letter"] not in by:
                        by[o2["letter"]] = o2
                    elif o2["correct"]:
                        by[o2["letter"]] = o2
                if set(by) == set("abcd"):
                    break
            if set(by) != set("abcd"):
                continue
            correct = next((L for L in "abcd" if by[L].get("correct")), None)
            if not correct:
                continue
            for o2 in by.values():
                for j, cand in enumerate(opts):
                    if j not in used and cand is o2:
                        used.add(j)
            cy = min(by[L]["y"] for L in "abcd")
            stem = nearest_stem(stems, cy, lo=5, hi=220)
            if not stem:
                # fallback line rebuild
                above = [
                    w
                    for w in words
                    if cy - 180 < w[1] < cy - 8
                    and re.search(r"[A-Za-z]{3,}", w[4])
                    and not WATERMARK.match(w[4])
                ]
                if not above:
                    continue
                buckets = {}
                for w in above:
                    buckets.setdefault(round(w[1], 0), []).append(w)
                yk = max(buckets)
                stem_text = clean(
                    " ".join(w[4] for w in sorted(buckets[yk], key=lambda x: x[0]))
                )
                if len(stem_text) < 12:
                    continue
            else:
                stem_text = stem["text"]
            if re.match(r"^[abcd](?:\.|\s)", stem_text) and len(stem_text) < 40:
                continue
            out.append(
                make_q(
                    "exam3",
                    "Exam 3 — English Questions Bank",
                    len(out) + 1,
                    stem_text,
                    by,
                    correct,
                )
            )
    return out


# ---------- MAX: numbered [n] + bold colored answers ----------
def extract_max():
    CORRECT_COLOR = 1398564
    doc = pymupdf.open(PDFS["max"])
    out = []
    seen = set()
    for page in doc:
        page_text = page.get_text("text")
        qmap = {}
        for m in re.finditer(r"\[(\d+)\]\s*(.+)", page_text):
            num = int(m.group(1))
            raw = m.group(2).split("\n")[0]
            qtext = clean(raw)
            qtext = re.sub(r"\s*@\s*\].*$", "", qtext)
            qtext = re.sub(r"^\s*\.+\s*", "", qtext)
            qtext = english_only(qtext) if not re.search(r"……", qtext) else clean(raw)
            # keep blanks
            if "……" not in qtext and "..." not in raw:
                qtext = clean(raw)
                qtext = re.sub(r"[^\x20-\x7E]+", " ", qtext.replace("\x03", " "))
                qtext = re.sub(r"\.{3,}", "……", qtext)
                qtext = re.sub(r"\s+", " ", qtext).strip()
            if len(qtext) < 12 or not re.search(r"[A-Za-z]{4,}", qtext):
                continue
            hits = page.search_for(f"[{num}]")
            y = hits[0].y0 if hits else 0
            if num not in qmap or hits:
                qmap[num] = {"text": qtext, "y": y}

        spans = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    spans.append(s)

        opts = []
        for s in spans:
            raw = s["text"]
            t = clean(raw)
            y = s["bbox"][1]
            x = s["bbox"][0]
            corr = (s["flags"] & 16) != 0 and s["color"] == CORRECT_COLOR
            m = re.match(r"^\(([abcd])\)\s*(.*)$", t, re.I)
            if m:
                txt = clean(m.group(2))
                txt = english_only(txt) if txt else ""
                opts.append(
                    {
                        "letter": m.group(1).lower(),
                        "text": txt,
                        "y": y,
                        "x": x,
                        "correct": corr,
                    }
                )
            elif re.match(r"^\(([abcd])\)$", t, re.I):
                opts.append(
                    {
                        "letter": t[1].lower(),
                        "text": "",
                        "y": y,
                        "x": x,
                        "correct": corr,
                    }
                )
            elif corr:
                et = english_only(t)
                if et and len(et) <= 60:
                    opts.append(
                        {"letter": "?", "text": et, "y": y, "x": x, "correct": True}
                    )

        nums = sorted(qmap)
        for i, num in enumerate(nums):
            st = qmap[num]
            y0 = st["y"]
            y1 = qmap[nums[i + 1]]["y"] if i + 1 < len(nums) else y0 + 240
            if y1 <= y0:
                y1 = y0 + 240
            group = [o for o in opts if y0 + 5 < o["y"] < y1]
            by = {}
            for o in group:
                if o["letter"] not in "abcd":
                    continue
                if o["letter"] not in by:
                    by[o["letter"]] = dict(o)
                else:
                    if o["text"] and (not by[o["letter"]]["text"] or o["correct"]):
                        by[o["letter"]]["text"] = o["text"]
                    if o["correct"]:
                        by[o["letter"]]["correct"] = True
            for o in group:
                if o["letter"] != "?" or not o["correct"]:
                    continue
                candidates = [L for L in "abcd" if L in by and abs(by[L]["y"] - o["y"]) < 14]
                if not candidates:
                    # also match by proximity in y only among empty-text correct letters
                    candidates = [
                        L
                        for L in "abcd"
                        if L in by and abs(by[L]["y"] - o["y"]) < 20
                    ]
                if not candidates:
                    continue
                marked = [L for L in candidates if by[L].get("correct")]
                if marked:
                    target = min(marked, key=lambda L: abs(by[L].get("x", 0) - o["x"]))
                else:
                    target = min(candidates, key=lambda L: abs(by[L].get("x", 0) - o["x"]))
                # append if letter already has partial text
                if by[target]["text"] and o["text"] not in by[target]["text"]:
                    # prefer longer / slash forms
                    if len(o["text"]) >= len(by[target]["text"]):
                        by[target]["text"] = o["text"]
                else:
                    by[target]["text"] = o["text"] or by[target]["text"]
                by[target]["correct"] = True

            if set(by) != set("abcd"):
                continue
            if not all(by[L].get("text") for L in "abcd"):
                continue
            correct = next((L for L in "abcd" if by[L].get("correct")), None)
            if not correct:
                continue
            choices = [by[L]["text"] for L in "abcd"]
            if len(set(c.lower() for c in choices)) < 2:
                continue
            if num in seen:
                continue
            seen.add(num)
            out.append(
                {
                    "sourceKey": "max",
                    "source": "Practice Model — Engineering Equivalency",
                    "qnum": num,
                    "question": st["text"],
                    "choices": choices,
                    "answer": ord(correct) - ord("a"),
                }
            )
    out.sort(key=lambda q: q["qnum"])
    return out


def validate(qs):
    clean_q = []
    seen_keys = set()
    for q in qs:
        if len(q.get("choices", [])) != 4:
            continue
        if q.get("answer") not in (0, 1, 2, 3):
            continue
        # soften length limit for slash answers
        if any(not c or len(c) > 100 for c in q["choices"]):
            continue
        q["choices"] = [re.sub(r"\bEL3OMDA\b", "", c, flags=re.I).strip() for c in q["choices"]]
        q["choices"] = [re.sub(r"\s+", " ", c).strip(" ,;") for c in q["choices"]]
        if any(len(c) < 1 for c in q["choices"]):
            continue
        q["question"] = q["question"].strip()
        min_q = 8 if BLANK in q["question"] else 10
        if len(q["question"]) < min_q:
            continue
        key = (q["sourceKey"], q["question"].lower(), tuple(c.lower() for c in q["choices"]))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        clean_q.append(q)
    return clean_q


def main():
    all_q = []
    stats = {}
    targets = {"exam1": 219, "exam2": 212, "exam3": 200, "max": 150}
    for name, fn in [
        ("exam1", extract_exam1),
        ("exam2", extract_exam2),
        ("exam3", extract_exam3),
        ("max", extract_max),
    ]:
        print(f"Extracting {name}...")
        try:
            raw = fn()
            qs = validate(raw)
        except Exception:
            import traceback

            traceback.print_exc()
            raw, qs = [], []
        stats[name] = len(qs)
        print(f"  raw={len(raw)} validated={len(qs)} target={targets[name]}")
        for q in qs[:1]:
            print(f"     Q: {q['question'][:70]}")
            print(f"     choices: {q['choices']} ANS={q['choices'][q['answer']]}")
        all_q.extend(qs)

    for i, q in enumerate(all_q, 1):
        q["id"] = f"{q['sourceKey']}-{q['qnum']}"
        q["globalId"] = i

    (OUT / "questions.json").write_text(
        json.dumps(all_q, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "questions.js").write_text(
        "window.QUESTIONS = " + json.dumps(all_q, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print("TOTAL", len(all_q), stats)
    for k, t in targets.items():
        print(f"  {k}: {stats.get(k, 0)}/{t}")


if __name__ == "__main__":
    main()
