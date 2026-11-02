// src/utils/nameHighlight.js
//
// A faint gold line around the words "Shams" / "Tahzib" wherever they appear
// on screen — just around the name, not the cell or paragraph holding it.
//
// How: the words are measured with Range.getClientRects() and thin boxes are
// drawn over them in a separate, click-through layer appended to <body>.
// React's DOM is never touched — splitting text nodes into wrapper spans
// would leave React holding detached nodes and crash on the next update.
//
// The boxes follow scrolling, resizing and re-renders, are clipped to any
// scrolling container (a table body, the main panel) so they never float
// over the topbar, and sit below modals and menus (z-index 5).

// Full-name forms first, so "Shams Tahzib" gets one box, not two side by side.
const MATCH = /shams\s*tahzib|tahzib\s*shams|shams|tahzib/gi;
const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'TITLE']);
const PAD_X = 3;
const PAD_Y = 1;

let started = false;

export function installNameHighlight(root = document.body) {
  if (started || typeof MutationObserver === 'undefined' || !root) return;
  started = true;

  const layer = document.createElement('div');
  layer.className = 'gold-name-layer';
  layer.setAttribute('aria-hidden', 'true');
  document.body.appendChild(layer);

  const nodes = new Set();           // text nodes currently containing a match
  const pool = [];                   // reusable box elements
  let dirty = true;
  let rescan = new Set([root]);

  const skipped = (el) => {
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      if (SKIP.has(e.tagName) || e.isContentEditable || e === layer) return true;
    }
    return false;
  };

  const consider = (textNode) => {
    MATCH.lastIndex = 0;
    if (MATCH.test(textNode.nodeValue || '') && !skipped(textNode.parentElement)) nodes.add(textNode);
    else nodes.delete(textNode);
  };

  const scan = (n) => {
    if (!n || n === layer || layer.contains(n)) return;
    if (n.nodeType === Node.TEXT_NODE) { consider(n); return; }
    if (n.nodeType !== Node.ELEMENT_NODE) return;
    const walker = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
    for (let t = walker.nextNode(); t; t = walker.nextNode()) consider(t);
  };

  // The visible area of an element: the viewport, cut down by every
  // ancestor that clips its overflow. Cached per element for one frame.
  const clipCache = new Map();
  const clipOf = (el) => {
    if (clipCache.has(el)) return clipCache.get(el);
    let box = { l: 0, t: 0, r: window.innerWidth, b: window.innerHeight };
    for (let e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') { box = null; break; }
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const r = e.getBoundingClientRect();
        box = { l: Math.max(box.l, r.left), t: Math.max(box.t, r.top), r: Math.min(box.r, r.right), b: Math.min(box.b, r.bottom) };
      }
    }
    clipCache.set(el, box);
    return box;
  };

  const draw = () => {
    clipCache.clear();
    let used = 0;
    for (const node of nodes) {
      if (!node.isConnected) { nodes.delete(node); continue; }
      const clip = clipOf(node.parentElement);
      if (!clip || clip.r <= clip.l || clip.b <= clip.t) continue;
      const text = node.nodeValue || '';
      MATCH.lastIndex = 0;
      for (let m = MATCH.exec(text); m; m = MATCH.exec(text)) {
        const range = document.createRange();
        range.setStart(node, m.index);
        range.setEnd(node, m.index + m[0].length);
        for (const rect of range.getClientRects()) {
          if (!rect.width || !rect.height) continue;
          const l = Math.max(rect.left - PAD_X, clip.l);
          const t = Math.max(rect.top - PAD_Y, clip.t);
          const r = Math.min(rect.right + PAD_X, clip.r);
          const b = Math.min(rect.bottom + PAD_Y, clip.b);
          if (r <= l || b <= t) continue;
          let box = pool[used];
          if (!box) { box = document.createElement('div'); box.className = 'gold-name-box'; layer.appendChild(box); pool.push(box); }
          box.style.transform = `translate(${l}px, ${t}px)`;
          box.style.width = `${r - l}px`;
          box.style.height = `${b - t}px`;
          box.style.display = '';
          used += 1;
        }
      }
    }
    for (let i = used; i < pool.length; i += 1) pool[i].style.display = 'none';
  };

  let queued = false;
  const frame = () => {
    queued = false;
    if (rescan.size) { const items = [...rescan]; rescan = new Set(); items.forEach(scan); dirty = true; }
    if (dirty) { dirty = false; draw(); }
  };
  const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(frame); } };

  new MutationObserver((mutations) => {
    let relevant = false;
    for (const m of mutations) {
      if (m.target === layer || layer.contains(m.target)) continue;
      relevant = true;
      if (m.type === 'characterData') rescan.add(m.target);
      else if (m.type === 'childList') m.addedNodes.forEach((n) => rescan.add(n));
    }
    if (relevant) { dirty = true; schedule(); }   // any change can move text
  }).observe(root, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['class', 'style', 'hidden', 'open'] });

  const reposition = () => { dirty = true; schedule(); };
  window.addEventListener('scroll', reposition, { capture: true, passive: true });
  window.addEventListener('resize', reposition, { passive: true });
  // Layout can shift without a DOM change (fonts loading, CSS transitions such
  // as the sidebar collapsing); a slow tick keeps the boxes honest. Cheap: it
  // only measures the few words that matched.
  setInterval(() => { if (nodes.size) reposition(); }, 700);

  schedule();
}
