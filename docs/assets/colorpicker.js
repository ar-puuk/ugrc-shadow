"use strict";

// A shadcn/ui-style color picker popover (see kibo-ui's ColorPicker, which shadcn.io's
// components/color-picker page wraps: a 2D saturation/value square, a hue slider, a checkerboard
// alpha slider, and an eyedropper) - reimplemented in plain JS/CSS since this site has no
// framework/build step, and is shared by every color property row in the property panel rather
// than mounting one instance per row (analogous to Dropdown, but more like a single native color
// dialog shared across triggers than a per-widget component).
//
// The hue/alpha sliders are plain draggable <div>s (a root + a thumb), NOT native
// <input type="range"> elements - matching what the reference actually is under the hood (Radix
// UI's Slider primitive: styled divs with pointer-drag logic), not a native form control. An
// earlier version of this file tried to reskin a real <input type="range"> instead, which meant
// fighting each browser engine's own vendor-prefixed pseudo-element model
// (::-webkit-slider-runnable-track vs ::-moz-range-track) just to draw a gradient on a track - a
// plain div has no such pseudo-elements to fight, and reuses the exact same pointer-drag approach
// already used for the square below.
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

/** Wires a plain <div> up as a 1D draggable slider (pointer drag + arrow-key/Home/End keyboard
 * support), calling `onSeek(value)` with a number clamped to [min, max]. No visual state lives
 * here - the caller re-renders (thumb position, track color, etc.) from inside `onSeek`. */
function wireLinearSlider(el, min, max, onSeek) {
  let dragging = false;
  const seekFromClientX = (clientX) => {
    const rect = el.getBoundingClientRect();
    const t = rect.width === 0 ? 0 : Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    onSeek(min + t * (max - min));
  };
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    dragging = true;
    el.setPointerCapture(e.pointerId);
    seekFromClientX(e.clientX);
  });
  el.addEventListener("pointermove", (e) => { if (dragging) seekFromClientX(e.clientX); });
  el.addEventListener("pointerup", (e) => { dragging = false; el.releasePointerCapture(e.pointerId); });
  el.addEventListener("keydown", (e) => {
    const current = Number(el.getAttribute("aria-valuenow")) || min;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") { e.preventDefault(); onSeek(Math.min(max, current + 1)); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") { e.preventDefault(); onSeek(Math.max(min, current - 1)); }
    else if (e.key === "Home") { e.preventDefault(); onSeek(min); }
    else if (e.key === "End") { e.preventDefault(); onSeek(max); }
  });
}

function makeSlider(labelText, min, max) {
  const el = document.createElement("div");
  el.className = "cp-slider";
  el.setAttribute("role", "slider");
  el.setAttribute("aria-label", labelText);
  el.setAttribute("aria-valuemin", String(min));
  el.setAttribute("aria-valuemax", String(max));
  el.tabIndex = 0;
  const thumb = document.createElement("div");
  thumb.className = "cp-slider-thumb";
  el.appendChild(thumb);
  return { el, thumb };
}

export class ColorPickerPopover {
  constructor() {
    this._onChange = null;
    this._triggerEl = null;
    this.hsv = { h: 0, s: 0, v: 0 };
    this.alpha = 100; // 0-100

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
    const hue = makeSlider("Hue", 0, 360);
    this.hueEl = hue.el; this.hueEl.classList.add("cp-hue-slider"); this.hueThumbEl = hue.thumb;
    const alpha = makeSlider("Alpha (transparency)", 0, 100);
    this.alphaEl = alpha.el; this.alphaEl.classList.add("cp-alpha-slider"); this.alphaThumbEl = alpha.thumb;
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
          this._syncVisuals();
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
    this.alpha = Math.round(alpha * 100);
    this._syncVisuals();
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

  /** Re-renders every visual piece (square background/thumb, hue thumb position, alpha thumb
   * position + track tint, preview chip, hex/alpha fields) from `this.hsv`/`this.alpha` - called
   * after any internal state change, regardless of which control caused it. */
  _syncVisuals() {
    const { h, s, v } = this.hsv;
    this.squareEl.style.background =
      `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent), hsl(${h}, 100%, 50%)`;
    this.thumbEl.style.left = `${s}%`;
    this.thumbEl.style.top = `${100 - v}%`;

    this.hueThumbEl.style.left = `${(h / 360) * 100}%`;
    this.hueEl.setAttribute("aria-valuenow", String(Math.round(h)));

    const { r, g, b } = this._currentRgb();
    this.alphaThumbEl.style.left = `${this.alpha}%`;
    this.alphaEl.setAttribute("aria-valuenow", String(Math.round(this.alpha)));
    // A CSS custom property rather than a plain style.background: .cp-alpha-slider's own
    // stylesheet rule layers this UNDER the static checkerboard (var(--checker-bg)) - setting
    // background directly here would wipe that second layer out instead of composing with it.
    this.alphaEl.style.setProperty("--cp-tint", `linear-gradient(to right, transparent, rgb(${r | 0}, ${g | 0}, ${b | 0}))`);
    this.previewEl.style.setProperty("--cp-preview-color", `rgba(${r | 0}, ${g | 0}, ${b | 0}, ${this.alpha / 100})`);

    this.hexInputEl.value = this._currentHex();
    this.alphaInputEl.value = String(Math.round(this.alpha));
  }

  _emit() {
    if (!this._onChange) return;
    const alphaFraction = this.alpha / 100;
    const { r, g, b } = this._currentRgb();
    const hex = rgbToHex(r, g, b);
    const formatted = alphaFraction >= 1
      ? hex
      : `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${Math.round(alphaFraction * 100) / 100})`;
    this._onChange(formatted);
  }

  _wireInteractions() {
    let draggingSquare = false;
    const moveSquare = (clientX, clientY) => {
      const rect = this.squareEl.getBoundingClientRect();
      const x = rect.width === 0 ? 0 : Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const y = rect.height === 0 ? 0 : Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
      this.hsv = { h: this.hsv.h, s: x * 100, v: (1 - y) * 100 };
      this._syncVisuals();
      this._emit();
    };
    this.squareEl.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      draggingSquare = true;
      this.squareEl.setPointerCapture(e.pointerId);
      moveSquare(e.clientX, e.clientY);
    });
    this.squareEl.addEventListener("pointermove", (e) => { if (draggingSquare) moveSquare(e.clientX, e.clientY); });
    this.squareEl.addEventListener("pointerup", (e) => { draggingSquare = false; this.squareEl.releasePointerCapture(e.pointerId); });

    wireLinearSlider(this.hueEl, 0, 360, (h) => {
      this.hsv = { ...this.hsv, h };
      this._syncVisuals();
      this._emit();
    });
    wireLinearSlider(this.alphaEl, 0, 100, (a) => {
      this.alpha = a;
      this._syncVisuals();
      this._emit();
    });

    this.hexInputEl.addEventListener("change", () => {
      const m = this.hexInputEl.value.trim().match(/^#?([0-9a-f]{6})$/i);
      if (!m) { this.hexInputEl.value = this._currentHex(); return; }
      const { r, g, b } = hexToRgb(`#${m[1]}`);
      this.hsv = rgbToHsv(r, g, b);
      this._syncVisuals();
      this._emit();
    });
    this.alphaInputEl.addEventListener("change", () => {
      const n = Math.max(0, Math.min(100, Math.round(Number(this.alphaInputEl.value))));
      if (Number.isNaN(n)) { this.alphaInputEl.value = String(Math.round(this.alpha)); return; }
      this.alpha = n;
      this._syncVisuals();
      this._emit();
    });
  }
}
