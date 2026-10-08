"""
ThemeSync — Phase 4 Evaluation Set (dashboard page)
=====================================================
Prepares the Phase 4 expert-rating set (Chapter 3, p. 54; design in
src/evaluation/phase4_packet.py) without hand-editing manifest.csv or
cropping logos by hand:

  1. Posters  — the unseen event posters in the set, each checked against
                the annotated YOLO images; add posters or set them aside.
  2. Details  — per poster, the event text the certificate and event ID
                carry, and which of Stage 0b's detected logos they use (or
                uploaded ones), with a preview of both outputs.
  3. Generate — every layout plus the private answer key.
  4. Packets  — one printable PDF and score sheet per expert.

It reads and writes the same data/raw/phase4_posters/manifest.csv and
logos/ folder as the CLI, and steps 3-4 run the CLI itself, so the two can
be mixed freely.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

import streamlit as st
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import components as ui                          # noqa: E402 — sets up sys.path; shared YOLO cache
import phase4_packet as p4                       # noqa: E402
import pipeline                                  # noqa: E402

_SRC, _ROOT = ui.SRC, ui.ROOT

POSTERS_DIR = p4.POSTERS_DIR
LOGOS_DIR = os.path.join(POSTERS_DIR, p4.LOGOS_DIRNAME)
SET_ASIDE_DIR = os.path.join(POSTERS_DIR, "_set_aside")
PREVIEW_DIR = os.path.join(p4.OUT_DIR, "preview")
PACKETS_DIR = os.path.join(p4.OUT_DIR, "packets")
P4_SCRIPT = os.path.join(_SRC, "evaluation", "phase4_packet.py")
N_POSTERS = 16

with open(p4.FORMATS["event_id"]) as _f:
    _ID_LIMITS = {k.strip("{}"): v.get("max_characters")
                  for k, v in json.load(_f)["variable_schema"].items()}
TITLE_MAX = _ID_LIMITS["Event_Title"]
HEADER_MAX = _ID_LIMITS["Organization_Header"]
DETAILS_MAX = _ID_LIMITS["Event_Details"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stem(poster_file: str) -> str:
    return os.path.splitext(poster_file)[0]


_safe_name = ui.safe_name
_detect = ui.detect
_crop = ui.crop
_tile = ui.tile


@st.cache_data(show_spinner="Checking the posters against the annotated YOLO images...")
def _seen(paths: tuple, mtimes: tuple) -> dict:
    return {os.path.basename(p): m for p, m in p4.seen_matches(list(paths)).items()}


def _logo_candidates(row: dict, poster_path: str) -> list:
    """Every logo Stage 0b detected on the poster (numbered in reading
    order, cropped exactly as the pipeline crops them), then any uploaded
    or previously saved logo files for it."""
    stem, mtime = _stem(row["poster_file"]), os.path.getmtime(poster_path)
    try:
        nodes = _detect(poster_path, mtime)
    except Exception as e:  # surfaced in the UI, not a hard crash
        st.warning(f"Stage 0b unavailable — {e}")
        nodes = []
    with Image.open(poster_path) as img:
        height = img.height
    auto = pipeline._select_logo_row(nodes, height)
    auto_boxes = [tuple(n["bbox"]) for n in auto]
    primary_box = (tuple(max(auto, key=lambda n: n.get("detection_confidence", 0.0))["bbox"])
                   if auto else None)

    logos = [n for n in nodes if n.get("semantic_category") == "logo"]
    logos.sort(key=lambda n: (round(n["bbox"][1] / (0.05 * height)), n["bbox"][0]))
    cands = []
    for k, n in enumerate(logos, start=1):
        box = tuple(n["bbox"])
        x, y = int(box[0]), int(box[1])
        cands.append({
            "id": f"det_{x}_{y}", "label": f"#{k}", "kind": "detected", "bbox": box,
            "x": box[0], "conf": n.get("detection_confidence", 0.0),
            "auto": box in auto_boxes, "primary": box == primary_box,
            "image": _crop(poster_path, mtime, box), "file": f"{stem}_det_{x}_{y}.png",
        })

    for c in cands:
        c["rel"] = f"{p4.LOGOS_DIRNAME}/{c['file']}"
    known = {c["file"] for c in cands}
    extra = []
    if os.path.isdir(LOGOS_DIR):
        extra += [os.path.join(LOGOS_DIR, f) for f in sorted(os.listdir(LOGOS_DIR))
                  if f.startswith(f"{stem}_upload_")]
    extra += p4.logo_paths(row, POSTERS_DIR) or []
    for path in extra:
        f = os.path.basename(path)
        if f in known or not os.path.exists(path):
            continue
        known.add(f)
        with Image.open(path) as img:
            cands.append({"id": f"file_{f}", "label": f.replace(f"{stem}_upload_", "") or f,
                          "kind": "file", "x": float("inf"), "auto": False, "primary": False,
                          "image": img.copy(), "file": f, "rel": os.path.relpath(path, POSTERS_DIR)})
    return cands


def _annotated_poster(poster_path: str, cands: list, ticked: set) -> Image.Image:
    """The poster with each detected logo boxed and numbered: green when
    ticked, red when not."""
    return ui.annotate(poster_path, [(c["label"], c["bbox"], ui.GREEN if c["id"] in ticked else ui.RED)
                                     for c in cands if c["kind"] == "detected"])


def _saved_ticks(row: dict, cands: list) -> tuple:
    """(ticked ids, seal id) as last saved: the manifest's logo_files, or,
    when it is blank, the pipeline's own automatic pick."""
    saved = [os.path.basename(p) for p in (p4.logo_paths(row, POSTERS_DIR) or [])]
    if saved:
        by_file = {c["file"]: c["id"] for c in cands}
        ids = [by_file[f] for f in saved if f in by_file]
        return set(ids), (ids[0] if ids else None)
    return ({c["id"] for c in cands if c["auto"]},
            next((c["id"] for c in cands if c["primary"]), None))


_reader = ui.reader


def _run_cli(args: list, label: str, total: int = None) -> tuple:
    """Runs phase4_packet.py, with a progress bar driven by its '[ n]' lines."""
    bar = st.progress(0.0, text=label) if total else None
    lines = []
    with st.spinner(label):
        proc = subprocess.Popen([sys.executable, "-u", P4_SCRIPT, *args], cwd=_ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for out in proc.stdout:
            lines.append(out.rstrip())
            m = re.match(r"\s*\[\s*(\d+)\]", out)
            if bar and m:
                bar.progress(min(1.0, int(m.group(1)) / total), text=f"{label} — {m.group(1)} of {total}")
        code = proc.wait()
    return code, lines


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

ui.top_bar(0, "Research tools · outside the three-step workflow", tool="Phase 4 Evaluation Set")
st.caption(f"Builds the blind expert-rating packet: {N_POSTERS} unseen event posters × certificate "
           "and event ID × GNN-guided and no-GNN baseline (Chapter 3, p. 54). Everything here is "
           "saved to data/raw/phase4_posters/manifest.csv, the same file the CLI uses.")

os.makedirs(POSTERS_DIR, exist_ok=True)
rows = p4.read_manifest(POSTERS_DIR)
files = p4.poster_files(POSTERS_DIR)
listed = {r["poster_file"] for r in rows}
new_files = [f for f in files if f not in listed]
if new_files:  # same as `phase4_packet.py template`
    rows += [{k: "" for k in p4.MANIFEST_FIELDS} | {"poster_file": f} for f in new_files]
    p4.write_manifest(POSTERS_DIR, rows)
rows.sort(key=lambda r: r["poster_file"])

# ---------------------------------------------------------------------------
# 1 · Posters
# ---------------------------------------------------------------------------
st.header("1 · Posters")

orphans = [r["poster_file"] for r in rows if r["poster_file"] not in files]
if orphans:
    st.warning("The manifest lists poster files that aren't in the folder (renamed or removed?): "
               + ", ".join(orphans))
    if st.button("Remove these rows from the manifest"):
        p4.write_manifest(POSTERS_DIR, [r for r in rows if r["poster_file"] not in orphans])
        st.rerun()
rows = [r for r in rows if r["poster_file"] in files]

paths = tuple(os.path.join(POSTERS_DIR, r["poster_file"]) for r in rows)
seen = _seen(paths, tuple(os.path.getmtime(p) for p in paths)) if rows else {}
if seen:
    st.error("These posters match images the YOLO detector was trained or validated on, so they "
             "aren't unseen. Set them aside and add others: "
             + ", ".join(f"{f} (≈ {m})" for f, m in seen.items()))

st.dataframe(
    [{"Poster": r["poster_file"],
      "Event title": r.get("event_title", "") or "—",
      "Date": r.get("event_date", "") or "—",
      "Venue": r.get("event_venue", "") or "—",
      "Logos": (f"manual pick ({len(p4.logo_paths(r, POSTERS_DIR))})"
                if p4.logo_paths(r, POSTERS_DIR) else "automatic"),
      "Unseen": "⚠ no" if r["poster_file"] in seen else "✓"} for r in rows],
    hide_index=True, width="stretch",
)
st.caption(f"{len(rows)} poster(s) in the set · {sum(bool(r.get('event_title', '').strip()) for r in rows)} "
           f"with an event title. \"Automatic\" means the logos ThemeSync crops by itself.")

add_col, aside_col = st.columns(2)
with add_col:
    with st.expander("➕ Add posters"):
        uploads = st.file_uploader("Unseen event posters", type=["png", "jpg", "jpeg", "webp"],
                                   accept_multiple_files=True,
                                   key=f"poster_upload_{st.session_state.get('poster_upload_n', 0)}")
        if uploads:
            added, skipped = [], []
            for up in uploads:
                name = _safe_name(up.name)
                dest = os.path.join(POSTERS_DIR, name)
                if os.path.exists(dest):
                    skipped.append(name)
                    continue
                with open(dest, "wb") as f:
                    f.write(up.getbuffer())
                added.append(name)
            if added:
                p4.write_manifest(POSTERS_DIR, rows + [{k: "" for k in p4.MANIFEST_FIELDS} | {"poster_file": n}
                                                       for n in added])
            if skipped:
                st.warning("Already in the set, skipped: " + ", ".join(skipped))
            st.session_state["poster_upload_n"] = st.session_state.get("poster_upload_n", 0) + 1
            if added:
                st.rerun()
with aside_col:
    with st.expander("🗂 Set a poster aside"):
        st.caption("Moves the image to phase4_posters/_set_aside/ and drops its manifest row. "
                   "Nothing is deleted.")
        aside = st.selectbox("Poster", [r["poster_file"] for r in rows], index=None,
                             placeholder="Choose a poster", key="aside_pick")
        if st.button("Set aside", disabled=not aside):
            os.makedirs(SET_ASIDE_DIR, exist_ok=True)
            shutil.move(os.path.join(POSTERS_DIR, aside), os.path.join(SET_ASIDE_DIR, aside))
            p4.write_manifest(POSTERS_DIR, [r for r in rows if r["poster_file"] != aside])
            st.rerun()

# ---------------------------------------------------------------------------
# 2 · Details
# ---------------------------------------------------------------------------
st.header("2 · Event details and logos")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))
if not rows:
    st.info("Add posters above to begin.")
else:
    pick = st.selectbox(
        "Poster", [r["poster_file"] for r in rows], key="detail_pick",
        format_func=lambda f: (lambda r: f"{'✓' if r.get('event_title', '').strip() else '○'}  {f}"
                               f"  —  {r.get('event_title') or 'no event title yet'}")(
                                   next(r for r in rows if r["poster_file"] == f)),
    )
    idx = next(i for i, r in enumerate(rows) if r["poster_file"] == pick)
    row = rows[idx]
    stem = _stem(pick)
    poster_path = os.path.join(POSTERS_DIR, pick)
    cands = _logo_candidates(row, poster_path)
    saved_ticked, saved_seal = _saved_ticks(row, cands)
    for c in cands:  # first visit: start from what's saved
        st.session_state.setdefault(f"{stem}_tick_{c['id']}", c["id"] in saved_ticked)

    img_col, form_col = st.columns([1, 1.25], gap="large")
    with form_col:
        st.subheader("Event text")
        title = st.text_input("Event title", value=row.get("event_title", ""), max_chars=TITLE_MAX,
                              key=f"{stem}_title",
                              help="The event's name as the poster shows it. Short names read best "
                                   "on the event ID; drop long taglines.")
        date = st.text_input("Date", value=row.get("event_date", ""), key=f"{stem}_date",
                             placeholder="e.g. September 12, 2026 — blank if the poster has none")
        venue = st.text_input("Venue", value=row.get("event_venue", ""), key=f"{stem}_venue",
                              placeholder="e.g. CSPC Gymnasium — blank if the poster has none")
        org_text = st.text_area(
            "Organization (one line each)", key=f"{stem}_org", height=80,
            value="\n".join(s.strip() for s in row.get("organization_header", "").split("|") if s.strip()),
            help="Line 1 is the certificate's issuing organization; lines 1-2 are the event ID "
                 "header. Blank means Camarines Sur Polytechnic Colleges.",
        )
        org_lines = [s.strip() for s in org_text.splitlines() if s.strip()]
        draft = dict(row, event_title=title.strip(), event_date=date.strip(), event_venue=venue.strip(),
                     organization_header=" | ".join(org_lines))
        if len(" · ".join(p for p in (draft["event_date"], draft["event_venue"]) if p)) > DETAILS_MAX:
            st.warning(f"Date and venue together run past the event ID's {DETAILS_MAX}-character limit.")
        if len("\n".join(org_lines[:2])) > HEADER_MAX:
            st.warning(f"The first two organization lines run past the event ID's {HEADER_MAX}-character limit.")
        if draft["event_title"]:
            cert = p4.content_for(draft, idx)["certificate"]
            st.caption(f"Certificate wording: *\"{cert['{{Citation_Body}}']}\"* — the name and role are "
                       "sample data that change per poster.")

        use_art = st.checkbox("Use the event's title artwork on the event ID", key=f"{stem}_title_art",
                              value=p4.use_title_artwork(row),
                              help="Untick when the artwork cut from the poster looks clipped or messy "
                                   "in the preview; the event ID then types the title.")
        draft["title_artwork"] = "" if use_art else "no"
        use_deco = st.checkbox("Use the poster's decorations (motifs)", key=f"{stem}_motifs",
                               value=p4.use_motifs(row),
                               help="Untick when a 'decoration' in the preview is really lettering, a "
                                    "stamp or a logo.")
        draft["motifs"] = "" if use_deco else "no"

        st.subheader("Logos")
        if not any(c["kind"] == "detected" for c in cands):
            st.info("Stage 0b found no logos on this poster. Upload them below.")
        for start in range(0, len(cands), 4):
            for c, col in zip(cands[start:start + 4], st.columns(4)):
                with col:
                    st.image(_tile(c["image"]), width="stretch")
                    note = f"conf {c['conf']:.2f}" if c["kind"] == "detected" else "uploaded"
                    st.checkbox(f"{c['label']} · {note}", key=f"{stem}_tick_{c['id']}")
        logo_uploads = st.file_uploader(
            "Add logos Stage 0b missed (transparent PNGs look best)", type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True, key=f"{stem}_logo_upload_{st.session_state.get(f'{stem}_upl_n', 0)}",
        )
        if logo_uploads:
            os.makedirs(LOGOS_DIR, exist_ok=True)
            for up in logo_uploads:
                name = f"{stem}_upload_{_safe_name(up.name)}"
                with open(os.path.join(LOGOS_DIR, name), "wb") as f:
                    f.write(up.getbuffer())
                st.session_state[f"{stem}_tick_file_{name}"] = True
            st.session_state[f"{stem}_upl_n"] = st.session_state.get(f"{stem}_upl_n", 0) + 1
            st.rerun()

        ticked = [c for c in cands if st.session_state.get(f"{stem}_tick_{c['id']}")]
        seal = None
        if ticked:
            ids = [c["id"] for c in ticked]
            default = saved_seal if saved_seal in ids else next(
                (c["id"] for c in ticked if c["primary"]),
                max(ticked, key=lambda c: c.get("conf", 0.0))["id"])
            seal = st.selectbox("Seal on the certificate", ids, index=ids.index(default),
                                key=f"{stem}_seal",
                                format_func=lambda i: next(c["label"] for c in cands if c["id"] == i),
                                help="The certificate shows one logo; the event ID shows every "
                                     "ticked logo in a row, this one first.")
        auto_ids = {c["id"] for c in cands if c["auto"]}
        auto_seal = next((c["id"] for c in cands if c["primary"]), None)
        is_auto = bool(ticked) and {c["id"] for c in ticked} == auto_ids and seal == auto_seal
        if not ticked:
            st.warning("No logos ticked. Generation would fall back to ThemeSync's automatic pick"
                       + (" (none found — a drawn badge)." if not auto_ids else "."))
        elif is_auto:
            st.caption("✓ This is ThemeSync's own automatic pick; it's recorded that way in the answer key.")
        else:
            st.caption("Manual pick: the ticked logos are saved to phase4_posters/logos/ and used "
                       "for both conditions; the answer key records it as manual.")

        def _save() -> None:
            if is_auto or not ticked:
                draft["logo_files"] = ""
            else:
                chosen = sorted(ticked, key=lambda c: (c["id"] != seal, c["x"]))
                os.makedirs(LOGOS_DIR, exist_ok=True)
                for c in chosen:
                    if c["kind"] == "detected":
                        c["image"].save(os.path.join(LOGOS_DIR, c["file"]))
                draft["logo_files"] = ";".join(c["rel"] for c in chosen)
            p4.write_manifest(POSTERS_DIR, [draft if r is row else r for r in rows])

        save_col, preview_col = st.columns(2)
        with save_col:
            if st.button("💾 Save", type="primary", disabled=not draft["event_title"], width="stretch"):
                _save()
                st.session_state["flash"] = f"Saved {pick}."
                st.rerun()
        with preview_col:
            preview_clicked = st.button("👁 Save and preview", disabled=not draft["event_title"],
                                        width="stretch")
        if preview_clicked:
            _save()
            saved_row = next(r for r in p4.read_manifest(POSTERS_DIR) if r["poster_file"] == pick)
            content = p4.content_for(saved_row, idx)
            logos = p4.logo_paths(saved_row, POSTERS_DIR)
            pngs = {}
            with st.spinner("Generating the certificate and event ID (GNN-guided)..."):
                for fmt in p4.FORMATS:
                    _, pngs[fmt] = p4.generate_sample(poster_path, content, fmt, "gnn",
                                                      os.path.join(PREVIEW_DIR, stem, fmt), logos,
                                                      use_wordmark=p4.use_title_artwork(saved_row),
                                                      use_motifs=p4.use_motifs(saved_row))
            st.session_state[f"{stem}_preview"] = {"pngs": pngs, "row": saved_row}
            st.rerun()

    with img_col:
        st.image(_annotated_poster(poster_path, cands, {c["id"] for c in ticked}), width="stretch")
        st.caption("Numbered boxes are the logos Stage 0b detected: green = ticked, red = not.")

    preview = st.session_state.get(f"{stem}_preview")
    if preview:
        st.markdown("**Preview** — GNN-guided; the packet also has the no-GNN baseline of each.")
        current = next(r for r in p4.read_manifest(POSTERS_DIR) if r["poster_file"] == pick)
        if current != preview["row"]:
            st.caption("The saved details changed after this preview; preview again to refresh it.")
        cert_col, id_col = st.columns([1.35, 1])
        with cert_col:
            st.image(preview["pngs"]["certificate"], caption="Certificate", width="stretch")
        with id_col:
            st.image(preview["pngs"]["event_id"], caption="Event ID", width="stretch")

# ---------------------------------------------------------------------------
# 3 · Generate
# ---------------------------------------------------------------------------
st.header("3 · Generate the layouts")
rows = [r for r in p4.read_manifest(POSTERS_DIR) if r["poster_file"] in files]
n_used = min(len(rows), N_POSTERS)
untitled = [r["poster_file"] for r in rows if not r.get("event_title", "").strip()]
key_exists = os.path.exists(p4.KEY_PATH)

st.write(f"{n_used} poster(s) × 2 formats × 2 conditions = **{n_used * 4} layouts** "
         "(about 4 seconds each), plus the private answer key.")
if len(rows) > N_POSTERS:
    st.info(f"The set has {len(rows)} posters; generation picks {N_POSTERS} of them at random "
            "(fixed seed, so the pick is repeatable).")
if untitled:
    st.warning("Still missing an event title: " + ", ".join(untitled))
replace = True
if key_exists:
    when = time.strftime("%B %d, %Y %H:%M", time.localtime(os.path.getmtime(p4.KEY_PATH)))
    st.warning(f"An answer key already exists (made {when}). Generating replaces it, and any packets "
               "built from it are moved to a packets_superseded_… folder, since their sample codes "
               "would no longer match.")
    # A fresh key per run, so every replacement needs its own tick.
    replace = st.checkbox("Replace the existing answer key",
                          key=f"replace_key_{st.session_state.get('generate_runs', 0)}")
if st.button("⚙ Generate all layouts", type="primary",
             disabled=bool(untitled or seen or not rows or not replace)):
    args = ["generate", "--n_posters", str(N_POSTERS)] + (["--overwrite"] if key_exists else [])
    code, lines = _run_cli(args, "Generating layouts", total=n_used * 4)
    st.session_state["generate_log"] = (code, lines)
    st.session_state["generate_runs"] = st.session_state.get("generate_runs", 0) + 1
    st.rerun()
if "generate_log" in st.session_state:
    code, lines = st.session_state["generate_log"]
    if code == 0:
        st.success("Layouts generated. " + " ".join(l.strip() for l in lines if "identical" in l))
    else:
        st.error("Generation stopped: " + (lines[-1].strip() if lines else f"exit code {code}"))
    with st.expander("Generation log"):
        st.code("\n".join(lines) or "(no output)", language=None)

# ---------------------------------------------------------------------------
# 4 · Packets
# ---------------------------------------------------------------------------
st.header("4 · Build a packet per expert")
st.caption("The answer key (data/phase4/phase4_key.csv) un-blinds the packet: keep it with the group "
           "and never give it to an expert. Print every packet in colour, on the same printer.")
if not os.path.exists(p4.KEY_PATH):
    st.info("Generate the layouts first.")
else:
    manifest_path = os.path.join(POSTERS_DIR, "manifest.csv")
    if os.path.getmtime(manifest_path) > os.path.getmtime(p4.KEY_PATH):
        st.warning("Poster details were saved after the layouts were generated. Generate again "
                   "before building packets, so the packet shows the latest details.")
    existing = (sorted(d for d in os.listdir(PACKETS_DIR) if os.path.isdir(os.path.join(PACKETS_DIR, d)))
                if os.path.isdir(PACKETS_DIR) else [])
    name_col, seed_col = st.columns([2, 1])
    with name_col:
        expert = st.text_input("Expert's name", key="expert_name")
    with seed_col:
        seed = st.number_input("Page-order seed", min_value=1, value=len(existing) + 1, step=1,
                               help="Use a different seed for each expert so each gets their own "
                                    "page order.")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", expert).strip("_")
    if slug and slug in existing:
        st.caption(f"A packet for {expert} already exists; building again replaces it.")
    if st.button("🖨 Build packet", type="primary", disabled=not slug):
        code, lines = _run_cli(["packet", "--expert", expert.strip(), "--order_seed", str(int(seed))],
                               "Building the packet (about a minute)")
        if code == 0:
            st.success(f"Packet built for {expert.strip()}.")
        else:
            st.error("Packet build stopped: " + (lines[-1].strip() if lines else f"exit code {code}"))
            with st.expander("Log"):
                st.code("\n".join(lines), language=None)
        if os.path.isdir(PACKETS_DIR):
            existing = sorted(d for d in os.listdir(PACKETS_DIR)
                              if os.path.isdir(os.path.join(PACKETS_DIR, d)))

    if existing:
        chosen = st.selectbox("Download a packet", existing, index=None, placeholder="Choose an expert")
        if chosen:
            folder = os.path.join(PACKETS_DIR, chosen)
            pdf = os.path.join(folder, f"packet_{chosen}.pdf")
            scores = os.path.join(folder, f"scores_{chosen}.csv")
            pdf_col, csv_col = st.columns(2)
            with pdf_col:
                if os.path.exists(pdf):
                    st.download_button(f"⬇ Packet PDF ({os.path.getsize(pdf) / 1e6:.0f} MB)",
                                       data=_reader(pdf), file_name=os.path.basename(pdf),
                                       mime="application/pdf", width="stretch")
            with csv_col:
                if os.path.exists(scores):
                    st.download_button("⬇ Score sheet (CSV)", data=_reader(scores),
                                       file_name=os.path.basename(scores), mime="text/csv",
                                       width="stretch")
