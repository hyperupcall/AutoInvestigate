/* model-info.js — the only models this app may use (see CHEAP_MODELS.md), with
 * their OpenRouter pages and current prices. Single source of truth for the
 * settings dropdown and the "Information" popup. Prices are USD per 1M tokens. */
(function () {
  const Hack = (window.Hack = window.Hack || {});

  const MODELS = [
    {
      id: 'meta-llama/llama-3.1-8b-instruct',
      name: 'Meta: Llama 3.1 8B Instruct',
      provider: 'Meta',
      url: 'https://openrouter.ai/meta-llama/llama-3.1-8b-instruct',
      input: 0.05,
      output: 0.08,
    },
    {
      id: 'google/gemma-3-4b-it',
      name: 'Google: Gemma 3 4B',
      provider: 'Google',
      url: 'https://openrouter.ai/google/gemma-3-4b-it',
      input: 0.05,
      output: 0.1,
    },
    {
      id: 'openai/gpt-oss-120b',
      name: 'OpenAI: gpt-oss-120b',
      provider: 'OpenAI',
      url: 'https://openrouter.ai/openai/gpt-oss-120b',
      input: 0.037,
      output: 0.17,
    },
  ];

  /** Strip the ":online" web-search suffix so a configured id maps to its base model. */
  function baseId(id) {
    return String(id || '').replace(/:online$/, '');
  }

  function byId(id) {
    return MODELS.find((m) => m.id === baseId(id)) || null;
  }

  /** "$0.05" / "$0.10" / "$0.037" — two decimals, or three when needed. */
  function price(n) {
    const v = Number(n);
    return '$' + (Number.isInteger(v * 100) ? v.toFixed(2) : v.toFixed(3));
  }

  Hack.modelInfo = { MODELS, baseId, byId, price };
})();