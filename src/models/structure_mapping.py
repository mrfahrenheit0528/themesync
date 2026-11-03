"""
ThemeSync — Master structure mapping (Stage 2 input)
=====================================================
Carries the master layout's composition into the target format (notes
§3.26). Table 1 maps an ingested element's bbox [x, y] to the GNN's initial
feature encoding (x_i, y_i), and Figure 2 lists "the structural hierarchy
parsed by the GNN" among the Visual DNA; this module is that mapping.

From Stage 0b's detections it locates, as fractions of the poster:
  logo    the organisational logo row (pipeline._select_logo_row)
  title   the event title (the largest title-sized text group)
  header  the organisation text between the logo row and the title
  details the first text below the title (date, venue), above the footer

and anchors the target's nodes with a counterpart there — logos, the
organisation header, the title and (event IDs) the details line. The GNN
starts from those anchors (graph_builder.structure_start: the others are
placed in order between them) and refines the whole into a clean layout.

Format conventions win over the master where they conflict: logos and the
organisation header are only anchored when the master has them above its
title (a footer logo row doesn't pull the ID's logo row to the bottom).
"""

import os
import sys

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DP = os.path.join(_SRC, "data_preprocessing")
if _DP not in sys.path:
    sys.path.append(_DP)

from stylistic_markers import text_groups, title_group_box  # noqa: E402

# Which target nodes have a counterpart on a master poster, by schema name.
ROLES = {
    "logo":    ("Logo",),                                    # Institution_Logo, Organization_Logos
    "header":  ("Organization_Header", "Issuing_Organization"),
    "title":   ("Event_Title", "Certificate_Title"),
    "details": ("Event_Details",),
}


def _centre(box, W, H):
    x, y, w, h = box
    return (x + w / 2.0) / W, (y + h / 2.0) / H


def master_structure(detected_nodes: list, image_w: float, image_h: float, logo_row: list) -> dict:
    """{role: (cx, cy)} fractions of the master, for the roles found."""
    W, H = float(image_w), float(image_h)
    found = {}
    title = title_group_box(detected_nodes, W, H)
    if title is None:
        return found
    found["title"] = _centre(title, W, H)
    title_top, title_bottom = title[1], title[1] + title[3]

    logo_bottom = None
    if logo_row:
        x0 = min(n["bbox"][0] for n in logo_row)
        y0 = min(n["bbox"][1] for n in logo_row)
        x1 = max(n["bbox"][0] + n["bbox"][2] for n in logo_row)
        y1 = max(n["bbox"][1] + n["bbox"][3] for n in logo_row)
        if y1 <= title_top + 0.02 * H:          # the row sits above the title
            found["logo"] = _centre([x0, y0, x1 - x0, y1 - y0], W, H)
            logo_bottom = y1

    groups = [g for g in text_groups(detected_nodes, W, H)
              if (g["bbox"][1] + g["bbox"][3] / 2.0) < 0.9 * H          # not the footer
              and not (abs(g["bbox"][1] - title[1]) < 1 and abs(g["bbox"][3] - title[3]) < 1)]
    above = [g for g in groups if g["bbox"][1] + g["bbox"][3] <= title_top + 0.01 * H
             and (logo_bottom is None or g["bbox"][1] >= logo_bottom - 0.01 * H)]
    if above:
        # nearest to the logo row (or the top of the poster)
        ref = logo_bottom if logo_bottom is not None else 0.0
        found["header"] = _centre(min(above, key=lambda g: abs(g["bbox"][1] - ref))["bbox"], W, H)
    below = [g for g in groups if g["bbox"][1] >= title_bottom - 0.01 * H]
    if below:
        found["details"] = _centre(min(below, key=lambda g: g["bbox"][1])["bbox"], W, H)
    return found


# Certificates are dense stacks with a conventional top-down order: only the
# master's logo row and organisation header carry over; an event ID is
# sparse enough to follow the master's title and details as well.
ROLES_BY_DOMAIN = {"academic_certificate": ("logo", "header")}


def anchors_for(stack_nodes: list, structure: dict, domain: str = None) -> dict:
    """{index in stack_nodes: (cx, cy)} for the target nodes whose role the
    master has. stack_nodes are the target's stacked nodes in
    spatial_hierarchy order."""
    allowed = ROLES_BY_DOMAIN.get(domain, tuple(ROLES))
    anchors = {}
    for i, node in enumerate(stack_nodes):
        name = node["node_id"].strip("{}")
        for role, keys in ROLES.items():
            if role in structure and role in allowed and any(k in name for k in keys):
                anchors[i] = structure[role]
                break
    return anchors


# ---------------------------------------------------------------------------
# Composition: which layout archetype follows the master (notes §3.31)
# ---------------------------------------------------------------------------

# Thresholds, as fractions of the poster.
CENTRE_BAND = 0.08     # a text group whose centre is within this of the axis is centred
SIDE_ART_AREA = 0.15   # a "large artwork" covers at least this much of the poster...
SIDE_ART_OFFSET = 0.12  # ...with its centre at least this far off the axis
PANEL_W, PANEL_H = 0.50, 0.20      # an underlay this wide and tall is a panel behind text
BAND_W, BAND_CY = 0.75, 0.85       # an underlay this wide, centred this low, is a footer band


def master_composition(detected_nodes: list, image_w: float, image_h: float) -> dict:
    """
    How the master is composed, from Stage 0b's detections:
      align      "center" or "left": how the text groups (footer excluded)
                 sit, weighted by area — the title usually decides
      side_art   "left"/"right" when the largest artwork (embellishment or
                 illustration, ≥ 15% of the poster) sits off the centre line
      panel      an underlay ≥ 50% wide and ≥ 20% tall behind the text
      footer_band an underlay ≥ 75% wide across the bottom
    plus a short `evidence` string for each cue found.
    """
    W, H = float(image_w), float(image_h)
    groups = [g for g in text_groups(detected_nodes, W, H)
              if g["bbox"][1] + g["bbox"][3] / 2.0 < 0.9 * H and g["bbox"][2] * g["bbox"][3] > 0.002 * W * H]
    share = {"center": 0.0, "left": 0.0, "right": 0.0}
    for g in groups:
        x, _, w, h = g["bbox"]
        off = (x + w / 2.0) / W - 0.5
        share["center" if abs(off) <= CENTRE_BAND else "left" if off < 0 else "right"] += w * h
    total = sum(share.values()) or 1.0
    align = "left" if share["left"] / total >= 0.5 else "center"
    out = {"align": align, "side_art": None, "panel": False, "footer_band": False, "evidence": []}
    if align == "left":
        out["evidence"].append(f"text left of the centre line ({share['left'] / total:.0%} of the text area)")

    art = [n for n in detected_nodes or [] if n.get("semantic_category") in ("embellishment", "illustration")]
    if art:
        x, y, w, h = max(art, key=lambda n: n["bbox"][2] * n["bbox"][3])["bbox"]
        off = (x + w / 2.0) / W - 0.5
        if w * h >= SIDE_ART_AREA * W * H and abs(off) >= SIDE_ART_OFFSET:
            out["side_art"] = "left" if off < 0 else "right"
            out["evidence"].append(f"a large artwork {out['side_art']} of centre ({w * h / (W * H):.0%} of the poster)")
    for n in detected_nodes or []:
        if n.get("semantic_category") != "underlay":
            continue
        x, y, w, h = n["bbox"]
        if w >= PANEL_W * W and h >= PANEL_H * H and not out["panel"]:
            out["panel"] = True
            out["evidence"].append(f"text on a panel ({w / W:.0%} × {h / H:.0%} of the poster)")
        elif w >= BAND_W * W and (y + h / 2.0) >= BAND_CY * H and not out["footer_band"]:
            out["footer_band"] = True
            out["evidence"].append("a full-width band along the bottom")
    return out


def archetype_for(composition: dict, domain: str) -> str:
    """The layout archetype (candidate_generator.ARCHETYPES) that follows
    the master's composition. In order: left-aligned text → left; a large
    artwork beside the text → art column (certificate) or left-aligned (ID:
    text beside the art); text on a panel → header banner (certificate) or
    floating card (ID); a footer band → full-width band (ID); else
    classic centred."""
    if not composition:
        return None
    is_id = domain == "identification_card"
    if composition.get("align") == "left":
        return "left"
    if composition.get("side_art"):
        return "left" if is_id else "split"
    if composition.get("panel"):
        return "card" if is_id else "banner"
    if composition.get("footer_band") and is_id:
        return "band"
    return "classic"
