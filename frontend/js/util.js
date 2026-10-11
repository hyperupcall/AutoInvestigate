/* util.js — tiny DOM + misc helpers. Attaches to window.Hack.util */
(function () {
  const Hack = (window.Hack = window.Hack || {});

  let counter = 0;
  function uid(prefix) {
    counter += 1;
    return `${prefix || 'id'}-${counter.toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  }

  /**
   * el('div', { class: 'x', onclick: fn }, [child, 'text'])
   * Attribute values: null/false are skipped; true sets a bare attribute;
   * `text` sets textContent; `html` sets innerHTML; `dataset` merges data-*.
   */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const key of Object.keys(attrs)) {
        const value = attrs[key];
        if (value == null || value === false) continue;
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = value;
        else if (key === 'html') node.innerHTML = value;
        else if (key === 'value') node.value = value;
        else if (key === 'dataset') Object.assign(node.dataset, value);
        else if (key === 'style' && typeof value === 'object') Object.assign(node.style, value);
        else if (key.startsWith('on') && typeof value === 'function') {
          node.addEventListener(key.slice(2).toLowerCase(), value);
        } else if (value === true) node.setAttribute(key, '');
        else node.setAttribute(key, value);
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    if (children == null || children === false) return;
    const list = Array.isArray(children) ? children : [children];
    for (const child of list) {
      if (child == null || child === false) continue;
      node.appendChild(
        typeof child === 'string' || typeof child === 'number'
          ? document.createTextNode(String(child))
          : child
      );
    }
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function truncate(value, max) {
    const s = String(value == null ? '' : value);
    return s.length > max ? s.slice(0, max - 1).trimEnd() + '…' : s;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function formatTime(ts) {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function timeAgo(ts) {
    const seconds = Math.max(1, Math.round((Date.now() - ts) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    return `${Math.round(minutes / 60)}h ago`;
  }

  /** Deterministic PRNG so a given idea always yields the same mock output. */
  function hashString(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i += 1) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makeRng(seedText) {
    const rng = mulberry32(hashString(String(seedText || 'seed')));
    return {
      next: rng,
      int(min, max) {
        return Math.floor(rng() * (max - min + 1)) + min;
      },
      pick(arr) {
        return arr[Math.floor(rng() * arr.length)];
      },
      chance(p) {
        return rng() < p;
      },
    };
  }

  /** Preserve focus + scroll while a container is re-rendered. */
  function preserveView(container, renderFn) {
    const active = document.activeElement;
    const inContainer = active && container.contains(active);
    const focusKey = inContainer ? active.dataset.focusKey || active.id || null : null;
    const selStart = inContainer && active.selectionStart != null ? active.selectionStart : null;
    const selEnd = inContainer && active.selectionEnd != null ? active.selectionEnd : null;

    const scrolls = [];
    container.querySelectorAll('[data-scroll-key]').forEach((node) => {
      scrolls.push({ key: node.dataset.scrollKey, top: node.scrollTop });
    });

    renderFn();

    if (focusKey) {
      const next = container.querySelector(`[data-focus-key="${focusKey}"]`) || document.getElementById(focusKey);
      if (next && next.focus) {
        next.focus();
        if (selStart != null && next.setSelectionRange) {
          try { next.setSelectionRange(selStart, selEnd); } catch (_) { /* not a text input */ }
        }
      }
    }
    scrolls.forEach(({ key, top }) => {
      const node = container.querySelector(`[data-scroll-key="${key}"]`);
      if (node) node.scrollTop = top;
    });
  }

  Hack.util = {
    uid, el, append, clear, escapeHtml, truncate, sleep,
    formatTime, timeAgo, hashString, mulberry32, makeRng, preserveView,
  };
})();
