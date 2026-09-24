"use strict";

// A shadcn/ui-style color picker popover (see kibo-ui's ColorPicker, which shadcn.io's
// components/color-picker page wraps: a 2D saturation/value square, a hue slider, a checkerboard
// alpha slider, and an eyedropper) - reimplemented in plain JS/CSS since this site has no
// framework/build step, and is shared by every color property row in the property panel rather
// than mounting one instance per row (analogous to Dropdown, but more like a single native color
// dialog shared across triggers than a per-widget component).
//
// Deliberately diverges from kibo-ui's alpha slider in one way: kibo's alpha track overlays the
// checkerboard with a generic transparent-to-black/white fade, which doesn't actually show what
// increasing alpha does to THIS color. This version fades the checkerboard into the current
// opaque color instead, which is the standard, immediately-recognizable "this controls
// transparency" idiom (used by browser devtools, Figma, Photoshop, etc.).

function hexToRgb(hex) {
  const m = hex.replace("#", "");
  return { r: parseInt(m.slice(0, 2), 16), g: parseInt(m.slice(2, 4), 16), b: parseInt(m.slice(4, 6), 16) };
}

function rgbToHex(r, g, b) {
  const h = (n) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

function rgbToHsv(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = 60 * (((g - b) / d) % 6);
    else if (max === g) h = 60 * ((b - r) / d + 2);
    else h = 60 * ((r - g) / d + 4);
  }
  if (h < 0) h += 360;
  return { h, s: max === 0 ? 0 : (d / max) * 100, v: max * 100 };
}

function hsvToRgb(h, s, v) {
  s /= 100; v /= 100;
  const c = v * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = v - c;
  let r1 = 0, g1 = 0, b1 = 0;
  if (h < 60) [r1, g1, b1] = [c, x, 0];
  else if (h < 120) [r1, g1, b1] = [x, c, 0];
  else if (h < 180) [r1, g1, b1] = [0, c, x];
  else if (h < 240) [r1, g1, b1] = [0, x, c];
  else if (h < 300) [r1, g1, b1] = [x, 0, c];
  else [r1, g1, b1] = [c, 0, x];
  return { r: (r1 + m) * 255, g: (g1 + m) * 255, b: (b1 + m) * 255 };
}

export class ColorPickerPopover {
  constructor() {
    this._onChange = null;
    this._triggerEl = null;
    this.hsv = { h: 0, s: 0, v: 0 };

    this.el = document.createElement("div");
    this.el.className = "cp-popover";
    this.el.hidden = true;
    this.el.setAttribute("role", "dialog");
    this.el.tabIndex = -1;

    this.squareEl = document.createElement("div");
    this.squareEl.className = "cp-square";
    this.thumbEl = document.createElement("div");
    this.thumbEl.className = "cp-square-thumb";
    this.squareEl.appendChild(this.thumbEl);

    const sliders = document.createElement("div");
    sliders.className = "cp-sliders";
    this.hueEl = document.createElement("input");
    this.hueEl.type = "range"; this.hueEl.className = "cp-hue"; this.hueEl.min = "0"; this.hueEl.max = "360"; this.hueEl.step = "1";
    this.hueEl.setAttribute("aria-label", "Hue");
    this.alphaEl = document.createElement("input");
    this.alphaEl.type = "range"; this.alphaEl.className = "cp-alpha"; this.alphaEl.min = "0"; this.alphaEl.max = "100"; this.alphaEl.step = "1";
    this.alphaEl.setAttribute("aria-label", "Alpha (transparency)");
    sliders.append(this.hueEl, this.alphaEl);

    const fields = document.createElement("div");
    fields.className = "cp-fields";
    this.previewEl = document.createElement("span");
    this.previewEl.className = "cp-preview";
    this.hexInputEl = document.createElement("input");
    this.hexInputEl.type = "text"; this.hexInputEl.className = "cp-hex-input"; this.hexInputEl.placeholder = "#rrggbb";
    this.hexInputEl.setAttribute("aria-label", "Hex color");
    this.alphaFieldWrap = document.createElement("div");
    this.alphaFieldWrap.className = "cp-alpha-field";
    this.alphaInputEl = document.createElement("input");
    this.alphaInputEl.type = "text"; this.alphaInputEl.inputMode = "numeric";
    this.alphaInputEl.setAttribute("aria-label", "Alpha percent");
    const pct = document.createElement("span");
    pct.textContent = "%";
    this.alphaFieldWrap.append(this.alphaInputEl, pct);
    fields.append(this.previewEl, this.hexInputEl, this.alphaFieldWrap);

    this.el.append(this.squareEl, sliders, fields);

    if (typeof window.EyeDropper === "function") {
      this.eyedropperBtn = document.createElement("button");
      this.eyedropperBtn.type = "button"; this.eyedropperBtn.className = "cp-eyedropper-btn";
      this.eyedropperBtn.title = "Pick a color from the screen"; this.eyedropperBtn.setAttribute("aria-label", "Pick a color from the screen");
      this.eyedropperBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m2 22 1-1h3l9-9"/><path d="M3 21v-3l9-9"/><path d="m15 6 3.4-3.4a2.1 2.1 0 1 1 3 3L18 9l.4.4a2.1 2.1 0 1 1-3 3l-3.8-3.8a2.1 2.1 0 1 1 3-3l.4.4Z"/></svg>';
      this.eyedropperBtn.addEventListener("click", async () => {
        try {
          const result = await new window.EyeDropper().open();
          const { r, g, b } = hexToRgb(result.sRGBHex);
          this.hsv = rgbToHsv(r, g, b);
          this._syncFromHsv();
          this._emit();
        } catch { /* user cancelled the eyedropper - not an error */ }
      });
      fields.appendChild(this.eyedropperBtn);
    }

    document.body.appendChild(this.el);
    this._wireInteractions();

    document.addEventListener("pointerdown", (e) => {
      if (this.isOpen && !this.el.contains(e.target) && e.target !== this._triggerEl) this.close();
    });
    document.addEventListener("keydown", (e) => {
      if (this.isOpen && e.key === "Escape") { this.close(); this._triggerEl?.focus(); }
    });
    window.addEventListener("resize", () => { if (this.isOpen) this._position(); });
  }

  get isOpen() {
    return !this.el.hidden;
  }

  /** Opens the popover anchored to `triggerEl`, seeded from `hex`/`alpha` (alpha 0-1).
   * `onChange(formattedColor)` fires live as the user drags/types - `formattedColor` is a
   * "#rrggbb" or "rgba(r, g, b, a)" string in this app's usual convention. */
  open(triggerEl, hex, alpha, onChange) {
    if (this.isOpen && this._triggerEl !== triggerEl) this.close();
    this._triggerEl = triggerEl;
    this._onChange = onChange;
    const { r, g, b } = hexToRgb(hex);
    this.hsv = rgbToHsv(r, g, b);
    this.alphaEl.value = String(Math.round(alpha * 100));
    this._syncFromHsv();
    this.el.hidden = false;
    this._position();
  }

  close() {
    this.el.hidden = true;
    this._onChange = null;
    this._triggerEl = null;
  }

  _position() {
    if (!this._triggerEl) return;
    const rect = this._triggerEl.getBoundingClientRect();
    const popRect = this.el.getBoundingClientRect();
    const margin = 8;
    let left = rect.left;
    if (left + popRect.width + margin > window.innerWidth) left = window.innerWidth - popRect.width - margin;
    left = Math.max(margin, left);
    let top = rect.bottom + 6;
    if (top + popRect.height + margin > window.innerHeight) top = rect.top - popRect.height - 6;
    this.el.style.left = `${left}px`;
    this.el.style.top = `${Math.max(margin, top)}px`;
  }

  _currentRgb() {
    return hsvToRgb(this.hsv.h, this.hsv.s, this.hsv.v);
  }

  _currentHex() {
    const { r, g, b } = this._currentRgb();
    return rgbToHex(r, g, b);
  }

  /** Re-renders every visual piece (square background/thumb, hue thumb, alpha track tint, preview
   * chip, hex field) from `this.hsv` + the alpha slider's current value - called after any
   * internal state change, regardless of which control caused it. */
  _syncFromHsv() {
    const { h, s, v } = this.hsv;
    this.squareEl.style.background =
      `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent), hsl(${h}, 100%, 50%)`;
    this.thumbEl.style.left = `${s}%`;
    this.thumbEl.style.top = `${100 - v}%`;
    this.hueEl.value = String(Math.round(h));

    const hex = this._currentHex();
    const { r, g, b } = this._currentRgb();
    // A custom property, not a direct style.backgroundImage: the checkerboard base lives in CSS on
    // .cp-alpha AND its ::-webkit-slider-runnable-track/::-moz-range-track pseudo-elements (JS can't
    // set inline styles on a pseudo-element directly), layered under this dynamic tint - custom
    // properties inherit from an element into its own pseudo-elements, so setting it here reaches
    // all three.
    this.alphaEl.style.setProperty("--cp-tint", `linear-gradient(to right, transparent, rgb(${r | 0}, ${g | 0}, ${b | 0}))`);
    this.previewEl.style.setProperty("--cp-preview-color", `rgba(${r | 0}, ${g | 0}, ${b | 0}, ${Number(this.alphaEl.value) / 100})`);
    this.hexInputEl.value = hex;
    this.alphaInputEl.value = this.alphaEl.value;
  }

  _emit() {
    if (!this._onChange) return;
    const alpha = Number(this.alphaEl.value) / 100;
    const { r, g, b } = this._currentRgb();
    const hex = rgbToHex(r, g, b);
    const formatted = alpha >= 1
      ? hex
      : `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${Math.round(alpha * 100) / 100})`;
    this._onChange(formatted);
  }

  _wireInteractions() {
    let dragging = false;
    const moveSquare = (clientX, clientY) => {
      const rect = this.squareEl.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
      this.hsv = { h: this.hsv.h, s: x * 100, v: (1 - y) * 100 };
      this._syncFromHsv();
      this._emit();
    };
    this.squareEl.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      dragging = true;
      this.squareEl.setPointerCapture(e.pointerId);
      moveSquare(e.clientX, e.clientY);
    });
    this.squareEl.addEventListener("pointermove", (e) => { if (dragging) moveSquare(e.clientX, e.clientY); });
    this.squareEl.addEventListener("pointerup", (e) => { dragging = false; this.squareEl.releasePointerCapture(e.pointerId); });

    this.hueEl.addEventListener("input", () => {
      this.hsv = { ...this.hsv, h: Number(this.hueEl.value) };
      this._syncFromHsv();
      this._emit();
    });
    this.alphaEl.addEventListener("input", () => {
      this.alphaInputEl.value = this.alphaEl.value;
      this.previewEl.style.setProperty(
        "--cp-preview-color",
        (() => { const { r, g, b } = this._currentRgb(); return `rgba(${r | 0}, ${g | 0}, ${b | 0}, ${Number(this.alphaEl.value) / 100})`; })()
      );
      this._emit();
    });
    this.hexInputEl.addEventListener("change", () => {
      const m = this.hexInputEl.value.trim().match(/^#?([0-9a-f]{6})$/i);
      if (!m) { this.hexInputEl.value = this._currentHex(); return; }
      const { r, g, b } = hexToRgb(`#${m[1]}`);
      this.hsv = rgbToHsv(r, g, b);
      this._syncFromHsv();
      this._emit();
    });
    this.alphaInputEl.addEventListener("change", () => {
      const n = Math.max(0, Math.min(100, Math.round(Number(this.alphaInputEl.value))));
      if (Number.isNaN(n)) { this.alphaInputEl.value = this.alphaEl.value; return; }
      this.alphaEl.value = String(n);
      this._syncFromHsv();
      this._emit();
    });
  }
}
