/* idea-handoff.js — a tiny cross-page channel for "Add to idea list".
 *
 * The Ideation View (ideation.html) and the workspace (index.html) are separate
 * pages, but both are served from the same origin (the navbar links are relative),
 * so localStorage is the shared channel between them:
 *   - the Ideation View pushes an idea here when you click "Add to idea list";
 *   - the workspace drains it into the Idea Evaluation queue on load, and again
 *     whenever the `storage` event fires (another tab pushed while it was open).
 *
 * The pending list survives a reload, so an idea added while the workspace is
 * closed is picked up the next time it opens. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const KEY = 'hack.pendingEvaluation';

  function read() {
    try {
      const raw = localStorage.getItem(KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (e) {
      return [];
    }
  }

  function write(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* private mode, quota, … */ }
  }

  /** Queue one idea for the workspace's Idea Evaluation column. */
  function push(idea) {
    const text = String((idea && idea.text) || '').trim();
    if (!text) return false;
    const list = read();
    if (list.some((item) => item.text === text)) return false;
    list.push({ text, source: (idea && idea.source) || 'ideation', addedAt: Date.now() });
    write(list);
    return true;
  }

  /** Return the pending ideas and clear them (the workspace consumes them once). */
  function drain() {
    const list = read();
    if (list.length) write([]);
    return list;
  }

  Hack.ideaHandoff = { KEY, read, write, push, drain };
})();
