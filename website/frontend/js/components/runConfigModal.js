/* components/runConfigModal.js — the popup shown by "Start Deeper Research".
 *
 * Lets you include or exclude agent groups for one research run. Every group is
 * selected by default; the chosen ids are handed to the run, so a run can use
 * all three groups, or just one. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let overlay = null;
  let bodyEl = null;

  /** The MCP servers an agent can use, as display names (falls back to the id). */
  function mcpNames(agent) {
    const byId = (Hack.mcpServers && Hack.mcpServers.byId) || {};
    return ((agent && agent.mcp_servers) || []).map((id) => (byId[id] && byId[id].name) || id);
  }

  function renderGroupRow(group, selected) {
    return el('label', { class: 'run-config-group' }, [
      el('input', {
        type: 'checkbox', checked: selected,
        onchange: () => actions.toggleRunConfigGroup(group.id),
      }),
      el('div', { class: 'run-config-group-body' }, [
        el('div', { class: 'run-config-group-head' }, [
          el('span', { class: 'group-name', text: group.name }),
          el('span', { class: 'tag', text: `${group.agents.length} agents` }),
        ]),
        group.blurb ? el('p', { class: 'group-blurb', text: group.blurb }) : null,
        el('ul', { class: 'run-config-agents' }, group.agents.map((a) =>
          el('li', { class: 'run-config-agent' }, [
            el('span', { class: 'run-config-agent-name', text: a.name }),
            el('span', { class: 'run-config-agent-model muted small', text: a.model || 'unknown model' }),
            el('span', { class: 'run-config-agent-mcp muted small', text: 'MCP: ' + (mcpNames(a).join(', ') || 'none') }),
          ]))),
      ]),
    ]);
  }

  function renderBody() {
    const rc = store.state.ui.runConfig;
    const groups = store.state.settings.groupPerspectives || [];
    const item = store.state.evaluation.queue.find((q) => q.id === rc.queueId);
    const selected = new Set(rc.selectedGroupIds);

    const rows = groups.map((g) => renderGroupRow(g, selected.has(g.id)));
    const count = rc.selectedGroupIds.length;

    return el('div', {}, [
      item ? el('p', { class: 'run-config-idea', text: truncate(item.text, 220) }) : null,
      el('div', { class: 'run-config-head' }, [
        el('span', { class: 'muted small', text: `${count} of ${groups.length} groups selected` }),
        el('div', { class: 'level-head-actions' }, [
          el('button', { class: 'link-btn', text: 'Select all', onclick: () => actions.setAllRunConfigGroups(true) }),
          el('button', { class: 'link-btn', text: 'Select none', onclick: () => actions.setAllRunConfigGroups(false) }),
        ]),
      ]),
      groups.length
        ? el('div', { class: 'run-config-groups' }, rows)
        : el('p', { class: 'muted small', text: 'No agent groups are configured.' }),
      el('div', { class: 'run-config-actions' }, [
        el('button', { class: 'btn small ghost', text: 'Cancel', onclick: () => actions.closeRunConfig() }),
        el('button', {
          class: 'btn small primary', text: 'Start research',
          disabled: count === 0,
          title: count === 0 ? 'Select at least one group' : 'Start the run with the selected groups',
          onclick: () => actions.confirmRunConfig(),
        }),
      ]),
    ]);
  }

  function mount(container) {
    root = container;

    bodyEl = el('div', { class: 'modal-body' });
    const dialog = el('div', { class: 'modal run-config-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Start Deeper Research' }),
          el('p', { class: 'muted small', text: 'Choose which agent groups take part in this run.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeRunConfig() }),
      ]),
      bodyEl,
    ]);

    overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeRunConfig() }, [dialog]);
    overlay.style.display = 'none';

    clear(root);
    root.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.runConfig.open) actions.closeRunConfig();
    });

    render();
  }

  function render() {
    if (!overlay) return;
    const open = store.state.ui.runConfig.open;
    overlay.style.display = open ? '' : 'none';
    if (!open) return;
    clear(bodyEl);
    bodyEl.appendChild(renderBody());
  }

  Hack.components.runConfigModal = { mount, render };
})();
