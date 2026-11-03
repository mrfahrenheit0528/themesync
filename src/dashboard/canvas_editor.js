// ThemeSync — Active Canvas editor (Figure 3). See canvas_editor.py.
//
// The rendered SVG is edited in place. Moving the pointer only previews:
// the node's <g> is translated (drag) or scaled (resize) locally. Releasing
// it sends ONE terminal event to Python — on-drop, on-resize-complete,
// lock-toggle, text-edit, undo, redo (Chapter 3, p.42: never a drag
// stream). The session re-solves, appends a state and re-renders; the new
// SVG arrives as new data.

const NS = "http://www.w3.org/2000/svg";
const SNAP_PX = 6;              // snapping distance, screen px
const HANDLE_PX = 10;           // resize handle size, screen px
const MIN_SIZE = 8;             // smallest box, canvas px
const NUDGE_COMMIT_MS = 700;    // arrow-key nudges are sent as one on-drop after this pause
const PENDING_TIMEOUT_MS = 60000;
const ASSET_TYPE = "application/x-themesync-asset";   // a tile dragged from the Images sidebar
const MAX_DROP = 10 * 1024 * 1024;                    // largest picture file dropped on the canvas
const HANDLES = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
const CURSORS = { nw: "nwse-resize", se: "nwse-resize", ne: "nesw-resize", sw: "nesw-resize",
                  n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize" };

// Images inside the SVG arrive once per browser session (canvas_editor.py
// replaces each data: URI with a ts-asset:<hash> token) and are kept here,
// across reruns and remounts.
const assetCache = (window.__themesyncAssets = window.__themesyncAssets || {});

const round1 = (v) => Math.round(v * 10) / 10;
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi));

function svgEl(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

function snapTo(pos, size, lines, tol) {
  // The moving box's start, centre or end onto the nearest line within tol.
  let best = null;
  for (const line of lines) {
    for (const off of [0, size / 2, size]) {
      const d = line - (pos + off);
      if (Math.abs(d) <= tol && (!best || Math.abs(d) < Math.abs(best.d))) best = { d, line };
    }
  }
  return best && { pos: pos + best.d, line: best.line };
}

class CanvasEditor {
  constructor(root) {
    this.root = root;
    const q = (s) => root.querySelector(s);
    this.stage = q(".ts-stage");
    this.host = q(".ts-host");
    this.textarea = q(".ts-editor");
    this.counter = q(".ts-count");
    this.busyEl = q(".ts-busy");
    this.selEl = q(".ts-sel");
    this.chipEl = q(".ts-chip");
    this.readout = q(".ts-readout");
    this.msg = q(".ts-msg");
    this.buttons = {};
    root.querySelectorAll("[data-act]").forEach((b) => (this.buttons[b.dataset.act] = b));

    this.data = null;
    this.version = null;
    this.svg = null;
    this.overlay = null;
    this.nodes = new Map();
    this.groups = new Map();
    this.sel = null;
    this.remoteSel = undefined;   // the selection Python last sent
    this.lastCommand = null;      // nonce of the last command from Python
    this.hover = null;
    this.drag = null;
    this.nudge = null;
    this.editing = null;
    this.pending = null;
    this.pendingTimer = null;
    this.seq = 0;
    this.askedAt = 0;

    this.listeners = [];
    this.on(root, "keydown", (e) => this.onKey(e));
    this.on(this.stage, "pointerdown", (e) => this.onDown(e));
    this.on(this.stage, "pointermove", (e) => this.onMove(e));
    this.on(this.stage, "pointerup", (e) => this.onUp(e));
    this.on(this.stage, "pointercancel", () => this.cancelDrag());
    this.on(this.stage, "pointerleave", () => this.setHover(null));
    this.on(this.stage, "dblclick", (e) => this.onDouble(e));
    // Pictures dropped on the canvas: an image file from the computer, or a
    // tile from the Images sidebar (views/orchestration.py); a click on a
    // tile adds it too, in the layout's largest empty space
    this.on(this.stage, "dragover", (e) => this.onDragOver(e));
    this.on(this.stage, "dragleave", () => this.root.classList.remove("ts-dropping"));
    this.on(this.stage, "drop", (e) => this.onDrop(e));
    this.on(document, "themesync-add-asset", (e) => this.addAsset(e.detail && e.detail.asset, null));
    this.on(this.textarea, "keydown", (e) => this.onEditorKey(e));
    this.on(this.textarea, "input", () => this.updateCounter());
    this.on(this.textarea, "blur", () => this.commitText());
    this.on(this.textarea, "pointerdown", (e) => e.stopPropagation());
    for (const [act, b] of Object.entries(this.buttons)) this.on(b, "click", () => this.action(act));
    this.resizeObserver = new ResizeObserver(() => this.redrawOverlay());
    this.resizeObserver.observe(this.stage);
    // Keep keyboard focus if Streamlit remounts the canvas while it has it.
    this.on(root, "focusin", () => (window.__themesyncCanvasFocus = true));
    this.on(root, "focusout", (e) => {
      if (e.relatedTarget && root.contains(e.relatedTarget)) return;     // into the text editor
      if (e.relatedTarget) { window.__themesyncCanvasFocus = false; return; }
      // Focus went nowhere: a click on the page (clear the flag) or the
      // canvas being removed for a remount (keep it).
      setTimeout(() => { if (root.isConnected) window.__themesyncCanvasFocus = false; }, 0);
    });
    if (window.__themesyncCanvasFocus) setTimeout(() => root.isConnected && root.focus({ preventScroll: true }), 0);
  }

  on(el, type, fn) {
    el.addEventListener(type, fn);
    this.listeners.push([el, type, fn]);
  }

  destroy() {
    for (const [el, type, fn] of this.listeners) el.removeEventListener(type, fn);
    this.resizeObserver.disconnect();
    clearTimeout(this.pendingTimer);
    clearTimeout(this.msgTimer);
    if (this.nudge) clearTimeout(this.nudge.timer);
    delete this.root.__ts;
  }

  // ---- data from Python ---------------------------------------------------

  update(data) {
    this.data = data;
    // One <style> per font family, sent the first time the typography uses it
    for (const [family, css] of Object.entries(data.fonts || {})) {
      if (document.getElementById(`themesync-fonts-${family}`)) continue;
      const style = document.createElement("style");
      style.id = `themesync-fonts-${family}`;
      style.textContent = css;
      document.head.appendChild(style);
    }
    Object.assign(assetCache, data.assets || {});
    this.root.style.setProperty("--ts-ar", String(data.width / data.height));
    this.nodes = new Map((data.nodes || []).map((n) => [n.id, n]));

    const acked = this.pending && data.ack === this.pending;
    const fresh = acked || data.version !== this.version;
    if (acked) this.setPending(null);
    if (data.version !== this.version) {
      if (!this.mount(data)) return;
    } else if (acked) {
      this.clearPreviews();      // the event was rejected or changed nothing
    }
    if ((data.fontFamilies || []).some((f) => !document.getElementById(`themesync-fonts-${f}`))) this.requestAssets();

    if (data.selected !== this.remoteSel) {        // changed in the Constraint Editor
      this.remoteSel = data.selected;
      if (!this.drag) this.sel = this.nodes.has(data.selected) ? data.selected : null;
    }
    if (this.sel && !this.nodes.has(this.sel)) this.sel = null;
    // An event's outcome replaces the message line; a rerun that only
    // syncs the selection leaves a local note (e.g. "a logo: ...") alone.
    if (data.error || data.warning) this.showMessage(data.error || data.warning, data.error ? "error" : "warn");
    else if (fresh) this.showMessage("", "");
    this.updateToolbar();
    this.redrawOverlay();
    // A command from the right-hand panel, run once (e.g. Edit text)
    const cmd = data.command;
    if (cmd && cmd.nonce !== this.lastCommand) {
      this.lastCommand = cmd.nonce;
      if (cmd.type === "edit" && this.nodes.has(cmd.node_id)) {
        this.select(cmd.node_id);
        setTimeout(() => this.openEditor(cmd.node_id), 0);
      }
    }
  }

  mount(data) {
    const missing = [];
    const text = (data.svg || "").replace(/ts-asset:([0-9a-f]{16})/g, (m, h) => {
      if (!assetCache[h]) missing.push(h);
      return assetCache[h] || "";
    });
    if (missing.length) {
      this.requestAssets();
      return false;
    }
    const doc = new DOMParser().parseFromString(text, "image/svg+xml");
    const parsed = doc.documentElement;
    if (!parsed || parsed.nodeName !== "svg" || doc.getElementsByTagName("parsererror").length) {
      this.showMessage("The canvas could not be displayed (SVG parse error).", true);
      return false;
    }
    const svg = document.importNode(parsed, true);
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.setAttribute("class", "ts-svg");
    this.host.replaceChildren(svg);
    this.svg = svg;
    this.groups = new Map();
    for (const g of svg.querySelectorAll("[data-node-id]")) {
      const id = g.getAttribute("data-node-id");
      const node = this.nodes.get(id);
      this.groups.set(id, g);
      // The whole box is clickable, not just the painted glyphs.
      if (node && node.kind !== "decor") {
        const [x, y, w, h] = node.bbox;
        g.insertBefore(svgEl("rect", { x, y, width: w, height: h, fill: "transparent",
                                       "pointer-events": "all", class: "ts-hit" }), g.firstChild);
      }
    }
    this.overlay = svgEl("g", { class: "ts-overlay" });
    svg.appendChild(this.overlay);
    this.version = data.version;
    this.drag = null;
    this.nudge = null;
    this.hideEditor();
    return true;
  }

  requestAssets() {
    const now = Date.now();
    if (now - this.askedAt < 10000) return;
    this.askedAt = now;
    this.showMessage("Loading the canvas…", false);
    this.trigger("event", { type: "need-assets", nonce: `${now}-assets` });
  }

  // ---- geometry -------------------------------------------------------------

  unitsPerPx() {
    const m = this.svg && this.svg.getScreenCTM();
    return m && m.a ? 1 / m.a : 1;
  }

  toCanvas(e) {
    const m = this.svg && this.svg.getScreenCTM();
    return m ? new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse()) : null;
  }

  stageRect(b) {
    const m = this.svg.getScreenCTM();
    const s = this.stage.getBoundingClientRect();
    const p0 = new DOMPoint(b[0], b[1]).matrixTransform(m);
    const p1 = new DOMPoint(b[0] + b[2], b[1] + b[3]).matrixTransform(m);
    return { left: p0.x - s.left, top: p0.y - s.top, width: p1.x - p0.x, height: p1.y - p0.y };
  }

  boxOf(id) {
    if (this.drag && this.drag.id === id && this.drag.moved) return this.drag.box;
    if (this.nudge && this.nudge.id === id) return this.nudge.box;
    return this.nodes.get(id).bbox;
  }

  bounds(node) {
    // Content stays on the canvas; a motif may bleed off it by half its size.
    const [, , w, h] = node.bbox;
    const W = this.data.width, H = this.data.height;
    return node.kind === "decor" ? [-w / 2, -h / 2, W - w / 2, H - h / 2] : [0, 0, W - w, H - h];
  }

  snapLines(id) {
    const W = this.data.width, H = this.data.height;
    const xs = [W / 2, ...(this.data.grid || [])];
    const ys = [H / 2];
    for (const n of this.nodes.values()) {
      if (n.id === id || n.kind === "decor") continue;
      const [x, y, w, h] = n.bbox;
      xs.push(x, x + w / 2, x + w);
      ys.push(y, y + h / 2, y + h);
    }
    return { xs, ys };
  }

  moveBox(d, dx, dy, snap) {
    const node = this.nodes.get(d.id);
    const [x, y, w, h] = d.orig;
    const [x0, y0, x1, y1] = this.bounds(node);
    let nx = clamp(x + dx, x0, x1), ny = clamp(y + dy, y0, y1);
    d.guides = null;
    if (snap) {
      const tol = SNAP_PX * this.unitsPerPx();
      d.lines = d.lines || this.snapLines(d.id);
      const sx = snapTo(nx, w, d.lines.xs, tol), sy = snapTo(ny, h, d.lines.ys, tol);
      if (sx) nx = clamp(sx.pos, x0, x1);
      if (sy) ny = clamp(sy.pos, y0, y1);
      d.guides = { x: sx ? sx.line : null, y: sy ? sy.line : null };
    }
    return [nx, ny, w, h];
  }

  resizeBox(d, dx, dy, keepRatio) {
    const node = this.nodes.get(d.id);
    const [x, y, w, h] = d.orig;
    const hd = d.handle;
    let l = x, t = y, r = x + w, b = y + h;
    if (hd.includes("w")) l = Math.min(x + dx, r - MIN_SIZE);
    if (hd.includes("e")) r = Math.max(r + dx, l + MIN_SIZE);
    if (hd.includes("n")) t = Math.min(y + dy, b - MIN_SIZE);
    if (hd.includes("s")) b = Math.max(b + dy, t + MIN_SIZE);
    if ((keepRatio || node.lockAspect) && hd.length === 2) {
      const ratio = w / h;
      let nw = r - l, nh = b - t;
      if (nw / nh > ratio) nw = nh * ratio; else nh = nw / ratio;
      if (hd.includes("w")) l = r - nw; else r = l + nw;
      if (hd.includes("n")) t = b - nh; else b = t + nh;
    }
    if (node.kind !== "decor") {
      l = Math.max(0, l); t = Math.max(0, t);
      r = Math.min(this.data.width, r); b = Math.min(this.data.height, b);
    }
    return [l, t, Math.max(MIN_SIZE, r - l), Math.max(MIN_SIZE, b - t)];
  }

  preview(id, orig, box) {
    const g = this.groups.get(id);
    if (!g) return;
    const [x, y, w, h] = orig, [nx, ny, nw, nh] = box;
    const sx = nw / w, sy = nh / h;
    g.setAttribute("transform", Math.abs(sx - 1) < 1e-6 && Math.abs(sy - 1) < 1e-6
      ? `translate(${nx - x} ${ny - y})`
      : `translate(${nx} ${ny}) scale(${sx} ${sy}) translate(${-x} ${-y})`);
  }

  clearPreviews() {
    for (const g of this.groups.values()) g.removeAttribute("transform");
  }

  // ---- pointer --------------------------------------------------------------

  onDown(e) {
    if (e.button !== 0 || !this.svg || this.pending) return;
    if (this.editing) { this.commitText(); return; }
    this.root.focus({ preventScroll: true });
    const p = this.toCanvas(e);
    if (!p) return;
    const handle = e.target.closest && e.target.closest(".ts-handle");
    if (handle && this.sel) {
      this.startDrag("resize", this.sel, p, e, handle.getAttribute("data-h"));
      return;
    }
    const g = e.target.closest && e.target.closest("[data-node-id]");
    const id = g && g.getAttribute("data-node-id");
    if (!id || !this.nodes.has(id)) {
      this.select(null);
      return;
    }
    this.flushNudge();
    this.select(id);
    this.startDrag("move", id, p, e);
  }

  startDrag(mode, id, p, e, handle) {
    const node = this.nodes.get(id);
    this.drag = { mode, id, handle, start: p, orig: [...node.bbox], box: [...node.bbox], moved: false,
                  pointerId: e.pointerId, guides: null, lines: null };
    try { this.stage.setPointerCapture(e.pointerId); } catch (err) { /* already released */ }
    e.preventDefault();
  }

  onMove(e) {
    const d = this.drag;
    if (!d) {
      const g = e.target.closest && e.target.closest("[data-node-id]");
      this.setHover(g ? g.getAttribute("data-node-id") : null);
      return;
    }
    const p = this.toCanvas(e);
    if (!p) return;
    const dx = p.x - d.start.x, dy = p.y - d.start.y;
    if (!d.moved && Math.hypot(dx, dy) < 3 * this.unitsPerPx()) return;
    d.moved = true;
    d.box = d.mode === "move" ? this.moveBox(d, dx, dy, !e.altKey) : this.resizeBox(d, dx, dy, e.shiftKey);
    this.preview(d.id, d.orig, d.box);
    this.redrawOverlay();
  }

  onUp() {
    const d = this.drag;
    if (!d) return;
    this.drag = null;
    try { this.stage.releasePointerCapture(d.pointerId); } catch (err) { /* not captured */ }
    if (!d.moved) {
      this.notifySelect();
      this.redrawOverlay();
      return;
    }
    const box = d.box.map(round1);
    this.nodes.get(d.id).preview = box;
    this.send({ type: d.mode === "move" ? "on-drop" : "on-resize-complete", node_id: d.id, bbox: box });
    this.redrawOverlay();
  }

  cancelDrag() {
    if (!this.drag) return;
    const g = this.groups.get(this.drag.id);
    if (g) g.removeAttribute("transform");
    this.drag = null;
    this.redrawOverlay();
  }

  onDouble(e) {
    if (this.pending || !this.svg) return;
    // With the pointer captured by the first click's drag, the browser
    // targets dblclick at the stage, so fall back to a hit test.
    const g = e.target.closest && e.target.closest("[data-node-id]");
    let id = g && g.getAttribute("data-node-id");
    if (!id) {
      const p = this.toCanvas(e);
      id = p && this.nodeAt(p);
    }
    if (!id || !this.nodes.has(id)) return;
    this.select(id);
    this.openEditor(id);
  }

  nodeAt(p) {
    // The topmost node whose box contains p: content is drawn above motifs.
    let hit = null;
    for (const n of this.nodes.values()) {
      const [x, y, w, h] = n.bbox;
      if (p.x >= x && p.x <= x + w && p.y >= y && p.y <= y + h && (!hit || hit.kind === "decor" || n.kind !== "decor")) {
        hit = n;
      }
    }
    return hit && hit.id;
  }

  setHover(id) {
    if (id === this.hover) return;
    this.hover = id;
    this.redrawOverlay();
  }

  select(id) {
    if (id === this.sel) return;
    this.sel = id;
    if (!this.msg.classList.contains("error")) this.showMessage("", "");   // a new selection clears notes
    this.updateToolbar();
    this.redrawOverlay();
  }

  notifySelect() {
    // Tell Python, so the Constraint Editor shows the same node.
    if (this.sel && this.sel !== this.remoteSel) {
      this.trigger("event", { type: "select", node_id: this.sel, nonce: `${Date.now()}-${++this.seq}` });
    }
  }

  // ---- keyboard -------------------------------------------------------------

  onKey(e) {
    if (this.editing || !this.data) return;
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key;
    if (mod && (key === "z" || key === "Z")) { e.preventDefault(); this.action(e.shiftKey ? "redo" : "undo"); return; }
    if (mod && (key === "y" || key === "Y")) { e.preventDefault(); this.action("redo"); return; }
    if (mod || e.altKey) return;
    if (key === "Tab" && this.sel) {           // with nothing selected, Tab leaves the canvas
      e.preventDefault();
      this.cycle(e.shiftKey ? -1 : 1);
      return;
    }
    if (!this.sel) return;
    const step = e.shiftKey ? 10 : 1;
    const arrows = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (arrows[key]) { e.preventDefault(); this.nudgeBy(...arrows[key]); return; }
    if (key === "l" || key === "L") { e.preventDefault(); this.action("lock"); return; }
    if (key === "Enter" || key === "F2") { e.preventDefault(); this.openEditor(this.sel); return; }
    if ((key === "Delete" || key === "Backspace") && !this.pending) {   // delete the element (undo brings it back)
      e.preventDefault();
      this.flushNudge();
      this.send({ type: "remove", node_id: this.sel });
      return;
    }
    if (key === "Escape") { e.preventDefault(); this.flushNudge(); this.select(null); }
  }

  cycle(dir) {
    const ids = [...this.nodes.keys()];
    if (!ids.length) return;
    this.flushNudge();
    const i = ids.indexOf(this.sel);
    this.select(ids[(i + dir + ids.length) % ids.length]);
    this.notifySelect();
  }

  nudgeBy(dx, dy) {
    if (this.pending) return;
    const id = this.sel;
    const node = this.nodes.get(id);
    if (!this.nudge || this.nudge.id !== id) {
      this.flushNudge();
      this.nudge = { id, orig: [...node.bbox], box: [...node.bbox], timer: null };
    }
    const nd = this.nudge;
    const [x0, y0, x1, y1] = this.bounds(node);
    nd.box = [clamp(nd.box[0] + dx, x0, x1), clamp(nd.box[1] + dy, y0, y1), nd.box[2], nd.box[3]];
    this.preview(id, nd.orig, nd.box);
    this.redrawOverlay();
    clearTimeout(nd.timer);
    nd.timer = setTimeout(() => this.flushNudge(), NUDGE_COMMIT_MS);
  }

  flushNudge() {
    const nd = this.nudge;
    if (!nd) return;
    this.nudge = null;
    clearTimeout(nd.timer);
    if (nd.box[0] === nd.orig[0] && nd.box[1] === nd.orig[1]) return;
    const box = nd.box.map(round1);
    this.nodes.get(nd.id).preview = box;
    this.send({ type: "on-drop", node_id: nd.id, bbox: box, via: "keyboard" });
    this.redrawOverlay();
  }

  // ---- text editing -----------------------------------------------------------

  openEditor(id) {
    const node = this.nodes.get(id);
    if (!node || this.pending) return;
    if (node.text == null) {
      this.showMessage(`${node.label} has no text to edit${node.note ? ` (${node.note})` : ""}. `
                       + "Drag it to move it, or use its handles to resize it.", false);
      return;
    }
    this.flushNudge();
    this.editing = id;
    const r = this.stageRect(node.bbox);
    const sw = this.stage.clientWidth, sh = this.stage.clientHeight;
    const width = Math.min(sw, Math.max(r.width, 240));
    const height = Math.min(sh, Math.max(r.height, node.text.includes("\n") ? 64 : 46));
    const ta = this.textarea;
    Object.assign(ta.style, {
      display: "block",
      left: `${clamp(r.left, 0, sw - width)}px`,
      top: `${clamp(r.top, 0, sh - height - 18)}px`,
      width: `${width}px`,
      height: `${height}px`,
    });
    if (node.maxLength) ta.setAttribute("maxlength", String(node.maxLength));
    else ta.removeAttribute("maxlength");
    ta.value = node.text;
    this.updateCounter();
    ta.focus({ preventScroll: true });
    ta.select();
  }

  updateCounter() {
    const node = this.editing && this.nodes.get(this.editing);
    const c = this.counter;
    if (!node) { c.style.display = "none"; return; }
    const ta = this.textarea;
    const n = ta.value.length;
    c.textContent = node.maxLength
      ? `${n}/${node.maxLength} · Enter saves · Shift+Enter new line · Esc cancels`
      : "Enter saves · Shift+Enter new line · Esc cancels";
    c.classList.toggle("over", !!node.maxLength && n > node.maxLength);
    Object.assign(c.style, { display: "block", left: ta.style.left,
                             top: `${ta.offsetTop + ta.offsetHeight}px` });
  }

  onEditorKey(e) {
    e.stopPropagation();
    if (e.key === "Escape") { e.preventDefault(); this.hideEditor(); this.root.focus({ preventScroll: true }); }
    else if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.commitText(); }
  }

  commitText() {
    const id = this.editing;
    if (!id) return;
    const text = this.textarea.value;
    this.hideEditor();
    this.root.focus({ preventScroll: true });
    const node = this.nodes.get(id);
    if (node && text !== node.text) this.send({ type: "text-edit", node_id: id, text });
  }

  hideEditor() {
    this.editing = null;
    this.textarea.style.display = "none";
    this.counter.style.display = "none";
  }

  // ---- toolbar and events ---------------------------------------------------

  action(act) {
    if (this.pending || !this.data) return;
    if (act === "undo" || act === "redo") {
      this.flushNudge();
      if (this.pending) return;
      if (this.data[act === "undo" ? "canUndo" : "canRedo"]) this.send({ type: act });
      return;
    }
    const node = this.sel && this.nodes.get(this.sel);
    if (!node) return;
    if (act === "lock") {
      this.flushNudge();
      if (!this.pending) this.send({ type: "lock-toggle", node_id: node.id, hard: !node.hard });
    } else if (act === "edit") {
      this.openEditor(node.id);
    }
  }

  // ---- pictures dropped or added from the sidebar -------------------------

  dropKind(e) {
    const types = [...((e.dataTransfer && e.dataTransfer.types) || [])];
    return types.includes(ASSET_TYPE) ? "asset" : types.includes("Files") ? "file" : null;
  }

  onDragOver(e) {
    if (!this.dropKind(e) || !this.data) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    this.root.classList.add("ts-dropping");
  }

  onDrop(e) {
    const kind = this.dropKind(e);
    this.root.classList.remove("ts-dropping");
    if (!kind || !this.data) return;
    e.preventDefault();
    const p = this.toCanvas(e);
    const at = p ? [round1(p.x), round1(p.y)] : null;
    if (kind === "asset") return this.addAsset(e.dataTransfer.getData(ASSET_TYPE), at);
    const file = [...e.dataTransfer.files].find((f) => /^image\/(png|jpeg|webp)$/.test(f.type));
    if (!file) return this.showMessage("Drop a PNG, JPG or WEBP picture.", true);
    if (file.size > MAX_DROP) return this.showMessage("That picture is over 10 MB.", true);
    if (this.pending) return;
    const reader = new FileReader();
    reader.onload = () => this.send({ type: "add-picture", name: file.name, data: reader.result, at });
    reader.readAsDataURL(file);
    this.showMessage(`Adding ${file.name}…`, false);
  }

  addAsset(asset, at) {
    if (!asset || !this.data || this.pending) return;
    this.send({ type: "add-picture", asset, at });
  }

  send(event) {
    event.nonce = `${Date.now()}-${++this.seq}`;
    this.setPending(event.nonce);
    this.showMessage("", false);
    this.trigger("event", event);
  }

  setPending(nonce) {
    this.pending = nonce;
    clearTimeout(this.pendingTimer);
    this.busyEl.classList.toggle("on", !!nonce);
    if (nonce) {
      this.pendingTimer = setTimeout(() => {
        this.setPending(null);
        this.clearPreviews();
        this.redrawOverlay();
        this.showMessage("No response from the server — try again.", true);
      }, PENDING_TIMEOUT_MS);
    } else {
      for (const n of this.nodes.values()) delete n.preview;
    }
    this.updateToolbar();
  }

  showMessage(text, kind) {
    // kind: "error", "warn", or "" (a plain note); true means "error".
    // Every message fades by itself, a note sooner, so none stays over
    // the canvas (a "no text to edit" note used to stay until new data).
    const k = kind === true ? "error" : kind || "";
    clearTimeout(this.msgTimer);
    this.msg.textContent = text;
    this.msg.classList.toggle("error", k === "error");
    this.msg.classList.toggle("warn", k === "warn");
    if (text) this.msgTimer = setTimeout(() => this.showMessage("", ""), k ? 8000 : 3500);
  }

  updateToolbar() {
    if (!this.data) return;
    const node = this.sel && this.nodes.get(this.sel);
    this.selEl.textContent = node ? node.label : "Click an element to select it";
    this.chipEl.textContent = node ? (node.hard ? "Hard · manual override" : "Soft · algorithmic") : "";
    this.chipEl.className = "ts-chip" + (node ? (node.hard ? " hard" : " soft") : "");
    const b = this.buttons;
    b.lock.disabled = !node || !!this.pending;
    (b.lock.querySelector(".ts-lbl") || b.lock).textContent = node && node.hard ? "Release (Soft)" : "Lock (Hard)";
    b.lock.classList.toggle("is-hard", !!(node && node.hard));
    b.lock.title = node && node.hard
      ? "Hand this element back to the algorithm (L)"
      : "Pin this element exactly where it is (L)";
    b.edit.disabled = !node || node.text == null || !!this.pending;
    b.edit.title = node && node.text == null ? `No text to edit${node.note ? ` (${node.note})` : ""}`
                                              : "Edit the text (Enter or double-click)";
    b.undo.disabled = !this.data.canUndo || !!this.pending;
    b.redo.disabled = !this.data.canRedo || !!this.pending;
    this.updateReadout();
  }

  updateReadout() {
    const node = this.sel && this.nodes.get(this.sel);
    if (!node) { this.readout.textContent = ""; return; }
    const [x, y, w, h] = node.preview || this.boxOf(node.id);
    this.readout.textContent = `X ${Math.round(x)} · Y ${Math.round(y)} · W ${Math.round(w)} · H ${Math.round(h)} px`;
  }

  // ---- overlay ----------------------------------------------------------------

  redrawOverlay() {
    const o = this.overlay;
    if (!o || !this.data || !this.svg) return;
    const k = this.unitsPerPx();
    const W = this.data.width, H = this.data.height;
    o.replaceChildren();

    const d = this.drag && this.drag.moved ? this.drag : null;
    // The X/Y/W/H readout shows on the canvas only while a node moves
    this.root.classList.toggle("ts-dragging", !!d || !!this.nudge);
    if ((d && d.mode === "move") || this.nudge) {
      // Formula 3.13's structural grid, and the lines the box snapped to
      for (const gx of this.data.grid || []) o.appendChild(svgEl("line", { x1: gx, y1: 0, x2: gx, y2: H, class: "ts-grid" }));
      if (d && d.guides) {
        if (d.guides.x != null) o.appendChild(svgEl("line", { x1: d.guides.x, y1: 0, x2: d.guides.x, y2: H, class: "ts-guide" }));
        if (d.guides.y != null) o.appendChild(svgEl("line", { x1: 0, y1: d.guides.y, x2: W, y2: d.guides.y, class: "ts-guide" }));
      }
    }
    for (const n of this.nodes.values()) {
      if (n.hard && n.id !== this.sel) this.drawLock(o, n.preview || n.bbox, k);
    }
    if (this.hover && this.hover !== this.sel && this.nodes.has(this.hover) && !d) {
      const [x, y, w, h] = this.boxOf(this.hover);
      o.appendChild(svgEl("rect", { x, y, width: w, height: h, class: "ts-hover" }));
    }
    if (this.sel && this.nodes.has(this.sel)) {
      const node = this.nodes.get(this.sel);
      const [x, y, w, h] = node.preview || this.boxOf(this.sel);
      o.appendChild(svgEl("rect", { x, y, width: w, height: h, class: "ts-selbox" + (node.hard ? " hard" : "") }));
      if (node.hard) this.drawLock(o, [x, y, w, h], k);
      if (!this.pending && !this.nudge) {
        const s = HANDLE_PX * k;
        const at = { nw: [x, y], n: [x + w / 2, y], ne: [x + w, y], e: [x + w, y + h / 2],
                     se: [x + w, y + h], s: [x + w / 2, y + h], sw: [x, y + h], w: [x, y + h / 2] };
        for (const hd of HANDLES) {
          if (hd.length === 1 && (hd === "n" || hd === "s" ? w : h) < 4 * s) continue;  // tiny box: corners only
          const [hx, hy] = at[hd];
          o.appendChild(svgEl("rect", { x: hx - s / 2, y: hy - s / 2, width: s, height: s, rx: s * 0.2,
                                        class: "ts-handle", "data-h": hd, style: `cursor:${CURSORS[hd]}` }));
        }
      }
    }
    this.updateReadout();
  }

  drawLock(o, box, k) {
    // A padlock badge on the box's top-right corner: a Hard node (Formula 3.10).
    const [x, y, w] = box;
    const g = svgEl("g", { class: "ts-lock", transform: `translate(${x + w} ${y}) scale(${k})` });
    g.appendChild(svgEl("circle", { cx: 0, cy: 0, r: 10 }));
    g.appendChild(svgEl("rect", { x: -4.5, y: -1.5, width: 9, height: 7, rx: 1.5 }));
    g.appendChild(svgEl("path", { d: "M -2.6 -1.5 V -3.6 A 2.6 2.6 0 0 1 2.6 -3.6 V -1.5" }));
    o.appendChild(g);
  }
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector(".ts-root");
  if (!root) return undefined;
  // The function runs again on every data change, but only the last cleanup
  // runs at unmount — so one editor lives on the root element across calls.
  if (!root.__ts) root.__ts = new CanvasEditor(root);
  const editor = root.__ts;
  editor.trigger = setTriggerValue;
  editor.update(data || {});
  return () => editor.destroy();
}
