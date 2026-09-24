"use strict";

// Used by docs/index.html - split out purely to keep that page's own inline script smaller.
// See the dd-* rules in its <style> block.

/** All currently-open dropdowns close when any other one opens or the page is clicked outside
 * of them - tracked here rather than per-instance so opening #2 doesn't need to know #1 exists. */
const openDropdowns = new Set();
document.addEventListener("click", (e) => {
  for (const dd of [...openDropdowns]) {
    if (!dd.container.contains(e.target)) dd.close();
  }
});

/** A combobox built from a <button> + absolutely-positioned <ul role="listbox"> (see the .dd*
 * CSS) instead of a native <select> - the popped-open list of a real <select> is native OS/
 * browser chrome that CSS can barely touch (background-color/color, a little padding in
 * Chromium - no rounded corners, no shadow, no per-row hover, no per-row description text).
 * Rendering the menu in our own DOM removes that ceiling. Exposes just enough of a <select>'s
 * shape (a `.value` getter/setter, a "change" event) that callers barely need to know it isn't
 * one. */
export class Dropdown extends EventTarget {
  constructor(container) {
    super();
    this.container = container;
    this.button = container.querySelector(".dd-button");
    this.label = container.querySelector(".dd-button-label");
    this.menu = container.querySelector(".dd-menu");
    this.options = {};
    this._value = null;
    this._activeKey = null;

    this.button.addEventListener("click", () => (this.open ? this.close() : this._openMenu()));
    this.button.addEventListener("keydown", (e) => {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        this._openMenu();
      }
    });
    this.menu.addEventListener("keydown", (e) => this._onMenuKeydown(e));
  }

  get open() {
    return openDropdowns.has(this);
  }

  setOptions(options) {
    this.options = options;
    this.menu.innerHTML = "";
    for (const [key, opt] of Object.entries(options)) {
      const li = document.createElement("li");
      li.className = "dd-option";
      li.id = `${this.container.id}-opt-${key}`;
      li.role = "option";
      li.dataset.value = key;

      const dot = document.createElement("span");
      dot.className = "dd-option-dot";
      dot.setAttribute("aria-hidden", "true");
      li.appendChild(dot);

      const text = document.createElement("span");
      text.className = "dd-option-text";
      const labelEl = document.createElement("span");
      labelEl.className = "dd-option-label";
      labelEl.textContent = opt.label;
      text.appendChild(labelEl);
      if (opt.description) {
        const descEl = document.createElement("span");
        descEl.className = "dd-option-desc";
        descEl.textContent = opt.description;
        text.appendChild(descEl);
      }
      li.appendChild(text);

      li.addEventListener("click", () => {
        this.value = key;
        this.close();
        this.button.focus();
      });
      li.addEventListener("mousemove", () => this._setActive(key));
      this.menu.appendChild(li);
    }
  }

  get value() {
    return this._value;
  }

  set value(key) {
    if (!this._setSelected(key)) return;
    this.dispatchEvent(new Event("change"));
  }

  /** Sets the selected value without dispatching "change" - for reverting a selection a caller
   * vetoed (e.g. the user cancelled a confirm() prompt) without re-triggering its own "change"
   * listener, which a plain `.value =` revert would do and could loop. */
  setValueSilently(key) {
    this._setSelected(key);
  }

  /** Returns true if `key` was valid and actually changed the selection. */
  _setSelected(key) {
    if (!(key in this.options)) return false;
    const changed = this._value !== key;
    this._value = key;
    this.label.textContent = this.options[key].label;
    for (const li of this.menu.children) {
      li.classList.toggle("is-selected", li.dataset.value === key);
      li.setAttribute("aria-selected", String(li.dataset.value === key));
    }
    return changed;
  }

  _setActive(key) {
    this._activeKey = key;
    for (const li of this.menu.children) {
      li.classList.toggle("is-active", li.dataset.value === key);
    }
    this.button.setAttribute("aria-activedescendant", `${this.container.id}-opt-${key}`);
  }

  _openMenu() {
    for (const dd of [...openDropdowns]) if (dd !== this) dd.close();
    openDropdowns.add(this);
    this.menu.hidden = false;
    this.button.setAttribute("aria-expanded", "true");
    this._setActive(this._value);
    this.menu.focus();
  }

  close() {
    openDropdowns.delete(this);
    this.menu.hidden = true;
    this.button.setAttribute("aria-expanded", "false");
  }

  _onMenuKeydown(e) {
    const keys = Object.keys(this.options);
    let idx = Math.max(keys.indexOf(this._activeKey), 0);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      this._setActive(keys[Math.min(idx + 1, keys.length - 1)]);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      this._setActive(keys[Math.max(idx - 1, 0)]);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      this.value = this._activeKey;
      this.close();
      this.button.focus();
    } else if (e.key === "Escape") {
      e.preventDefault();
      this.close();
      this.button.focus();
    } else if (e.key === "Tab") {
      this.close();
    }
  }
}
