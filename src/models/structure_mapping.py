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
