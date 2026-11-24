const DEFAULT_ROUTE = 'verify';
const NO_FILE_LABEL = 'No file chosen';
const REDACTED = '[redacted]';
const RISK_COLUMN = 'wrong_release_count';
const KEY_PATTERN = /(sk-[\w-]{10,}|AKIA[0-9A-Z]{12,}|AIza[\w-]{20,}|gh[pousr]_\w{20,}|Bearer\s+[\w.-]{10,})/g;
const OCR_PRIORITY = [RISK_COLUMN, 'provider_id', 'status', 'reason', 'field_accuracy', 'release_accuracy', 'p50_s', 'p95_s', 'pages', 'est_cost_usd', 'refusal_codes'];
const FACT_FIELDS = [
  ['Currency', 'currency'],
  ['Opening balance', 'opening_balance'],
  ['Closing balance', 'closing_balance'],
  ['Rows', 'row_count'],
  ['Transactions', 'transaction_count'],
];
const ROUTES = {
  setup: renderSetup,
  verify: renderVerify,
  results: renderResults,
  benchmarks: renderBenchmarks,
  skills: renderSkills,
};
const RESULT_RENDERERS = {
  'ocr-compare': renderOcrCompare,
  'speed-bench': renderTables,
  'screenshot-bench': renderTables,
  'model-context-bench': renderTables,
  'token-cost': renderTokenCost,
  'risk-coverage': renderTables,
};

const view = document.getElementById('view');
let routeToken = 0;

function redactText(text) {
  return text.replace(KEY_PATTERN, REDACTED);
}

function redactSecret(value, secret) {
  if (!secret) return value;
  if (typeof value === 'string') return value.split(secret).join(REDACTED);
  if (Array.isArray(value)) return value.map(item => redactSecret(item, secret));
  if (isPlainObject(value)) return Object.fromEntries(Object.entries(value).map(([key, item]) => [key.split(secret).join(REDACTED), redactSecret(item, secret)]));
  return value;
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function humanize(key) {
  return key.replace(/_/g, ' ');
}

function formatValue(value) {
  if (value === null || value === undefined) return '-';
  return redactText(typeof value === 'object' ? JSON.stringify(value) : String(value));
}

function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = redactText(String(options.text));
  Object.assign(node.style, options.style ?? {});
  for (const [name, value] of Object.entries(options.attrs ?? {})) node.setAttribute(name, value);
  for (const [type, handler] of Object.entries(options.on ?? {})) node.addEventListener(type, handler);
  node.append(...children);
  return node;
}

function badge(label, tone) {
  return el('span', { className: `badge badge-${tone}`, text: label });
}

function alertBox(message, tone = 'error') {
  return el('div', { className: `alert alert-${tone}`, text: message, attrs: { role: 'alert' } });
}

async function fetchJson(path, init) {
  const response = await fetch(path, init?.method === 'POST' ? { ...init, headers: { ...init.headers, 'X-OB-UI': '1' } } : init);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Server returned an invalid response (HTTP ${response.status}).`);
  }
  if (!response.ok) throw new Error(typeof data?.error === 'string' ? data.error : `HTTP ${response.status}`);
  return data;
}

function currentRoute() {
  const name = location.hash.replace(/^#/, '');
  return Object.hasOwn(ROUTES, name) ? name : DEFAULT_ROUTE;
}

function markNav(route) {
  for (const link of document.querySelectorAll('[data-route]')) {
    if (link.dataset.route === route) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
}

async function renderRoute() {
  const route = currentRoute();
  const token = ++routeToken;
  markNav(route);
  view.replaceChildren(el('p', { text: 'Loading...' }));
  try {
    const page = await ROUTES[route]();
    if (token === routeToken) view.replaceChildren(page);
  } catch (error) {
    if (token === routeToken) view.replaceChildren(alertBox(`Could not load ${route}: ${error.message}`));
  }
}

function renderSetup() {
  return fetchJson('/api/providers').then(data => el('section', {}, [
    el('h2', { text: 'Setup' }),
    renderDefaults(data),
    renderRemoteGate(data.remote_enabled === true),
    renderProviderTable(Array.isArray(data.providers) ? data.providers : []),
    renderEnvHelp(),
  ]));
}

function renderDefaults(data) {
  return el('p', { className: 'defaults' }, [
    el('span', { text: 'Default provider: ' }),
    el('strong', { text: data.default ?? 'none' }),
    el('span', { text: ' · Fallback: ' }),
    el('strong', { text: data.fallback ?? 'none' }),
  ]);
}

function renderRemoteGate(enabled) {
  return el('div', { className: 'remote-gate' }, [
    el('h3', { text: 'Remote OCR' }),
    badge(enabled ? 'Enabled' : 'Disabled', enabled ? 'warn' : 'ok'),
    el('p', {
      text: 'Remote OCR sends page images off this machine to a third-party provider. It is off by default. '
        + 'To use it, the server must start with OPENBOOKS_ALLOW_REMOTE_OCR=1 set in its shell, '
        + 'and each request requires your explicit consent.',
    }),
  ]);
}

function renderProviderTable(providers) {
  const labels = ['Provider', 'Engine', 'Remote', 'Status', 'Issue', 'Env vars'];
  const head = el('tr', {}, labels.map(label => el('th', { text: label, attrs: { scope: 'col' } })));
  return el('table', { className: 'providers' }, [
    el('thead', {}, [head]),
    el('tbody', {}, providers.map(renderProviderRow)),
  ]);
}

function renderProviderRow(provider) {
  return el('tr', {}, [
    el('td', { text: provider.id }),
    el('td', { text: provider.engine }),
    el('td', {}, [provider.remote ? badge('Remote', 'warn') : badge('Local', 'ok')]),
    el('td', {}, [provider.available ? badge('Available', 'ok') : badge('Unavailable', 'bad')]),
    el('td', { text: provider.issue ?? '' }),
    el('td', {}, (provider.env ?? []).map(renderEnvVar)),
  ]);
}

function renderEnvVar(variable) {
  return el('div', { className: 'env-var' }, [
    el('code', { text: variable.name }),
    variable.set ? badge('set', 'ok') : badge('unset', 'muted'),
  ]);
}

function renderEnvHelp() {
  return el('div', { className: 'env-help' }, [
    el('h3', { text: 'Adding keys' }),
    el('p', {
      text: 'Set provider credentials as environment variables in the shell that starts the server, then reload this page. '
        + 'For Azure, you can also enter a key for a single verification; it is cleared after the request.',
    }),
  ]);
}

async function renderVerify() {
  const providers = await fetchJson('/api/providers');
  const resultSlot = el('div', { className: 'verify-result', attrs: { 'aria-live': 'polite' } });
  return el('section', {}, [
    el('h2', { text: 'Verify a document' }),
    buildVerifyForm(resultSlot, providers),
    resultSlot,
  ]);
}

function buildVerifyForm(resultSlot, providerData) {
  const fileInput = el('input', { attrs: { type: 'file', id: 'verify-file', name: 'file', 'aria-label': 'Document to verify' } });
  const fileName = el('p', { className: 'file-name', text: NO_FILE_LABEL });
  const dropzone = el('div', { className: 'dropzone' }, [
    el('p', { text: 'Drop a bank statement, settlement report, or tax document here.' }),
    fileInput,
    fileName,
  ]);
  wireDropzone(dropzone, fileInput, fileName);
  const providers = Array.isArray(providerData.providers) ? providerData.providers : [];
  const select = el('select', { attrs: { id: 'verify-provider', name: 'provider', required: '' } });
  const consent = el('input', { attrs: { type: 'checkbox', id: 'verify-consent', name: 'remote_consent', value: 'true' } });
  const apiKey = el('input', { attrs: { type: 'password', id: 'verify-api-key', name: 'api_key', autocomplete: 'off' } });
  const keyField = field('Azure API key (optional if set in the server environment)', apiKey);
  const needsAzureKey = provider => provider.engine === 'azure_docintel' && (provider.env ?? []).some(variable => variable.name === 'AZURE_DOCINTEL_KEY' && !variable.set);
  const canSupplyKey = provider => needsAzureKey(provider) && (provider.env ?? []).filter(variable => !variable.set).every(variable => variable.name === 'AZURE_DOCINTEL_KEY');
  const consentField = el('div', { className: 'field remote-consent' }, [
    consent,
    el('label', { text: 'I consent to sending document images to this remote OCR provider.', attrs: { for: consent.id } }),
  ]);
  const providerHint = el('p', { className: 'provider-hint', attrs: { 'aria-live': 'polite' } });
  select.append(el('option', { text: 'Choose an OCR provider', attrs: { value: '' } }));
  for (const provider of providers) {
    const disabled = (!provider.available && !canSupplyKey(provider)) || (provider.remote && !providerData.remote_enabled);
    const reason = provider.issue || (provider.remote && !providerData.remote_enabled ? 'remote OCR disabled' : '');
    const option = el('option', { text: `${provider.id}${provider.remote ? ' (remote)' : ' (local)'}${disabled ? ` — ${reason || 'unavailable'}` : ''}`, attrs: { value: provider.id } });
    option.disabled = disabled;
    select.append(option);
  }
  const preferred = providers.find(provider => provider.id === 'tesseract' && provider.available)
    ?? providers.find(provider => provider.id === providerData.default && provider.available && !provider.remote);
  if (preferred) select.value = preferred.id;
  function updateProvider() {
    const provider = providers.find(item => item.id === select.value);
    const remote = provider?.remote === true;
    consentField.hidden = !remote;
    consent.required = remote;
    const azure = provider?.engine === 'azure_docintel';
    keyField.hidden = !azure;
    apiKey.disabled = !azure;
    apiKey.required = azure && needsAzureKey(provider);
    if (!azure) apiKey.value = '';
    if (!remote) consent.checked = false;
    providerHint.textContent = remote ? 'This provider sends document images to a third party.' : 'Choose an available OCR provider.';
  }
  select.addEventListener('change', updateProvider);
  updateProvider();
  const form = el('form', { className: 'verify-form' }, [
    dropzone,
    field('OCR provider', select),
    providerHint,
    keyField,
    consentField,
    field('Currency', el('input', { attrs: { type: 'text', id: 'verify-currency', name: 'currency', placeholder: 'e.g. USD', pattern: '[A-Za-z]{3}', maxlength: '3', title: 'Enter a three-letter currency code' } })),
    field('Date order', el('select', { attrs: { id: 'verify-date-order', name: 'date_order' } }, [
      el('option', { text: 'Automatic', attrs: { value: '' } }),
      el('option', { text: 'Day / month / year', attrs: { value: 'dmy' } }),
      el('option', { text: 'Month / day / year', attrs: { value: 'mdy' } }),
    ])),
    field('Opening balance', el('input', { attrs: { type: 'text', id: 'verify-opening', name: 'opening', inputmode: 'decimal', placeholder: 'Optional', pattern: '[+\\-]?([0-9]+\\.?[0-9]*|\\.[0-9]+)', title: 'Enter a plain number without separators' } })),
    el('button', { className: 'primary', attrs: { type: 'submit' }, text: 'Verify' }),
  ]);
  form.addEventListener('submit', event => submitVerify(event, resultSlot));
  return form;
}

function field(labelText, input) {
  return el('div', { className: 'field' }, [el('label', { text: labelText, attrs: { for: input.id } }), input]);
}

function wireDropzone(zone, fileInput, fileName) {
  const setDragging = active => zone.classList.toggle('dragging', active);
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    setDragging(true);
  });
  zone.addEventListener('dragleave', () => setDragging(false));
  zone.addEventListener('drop', event => {
    event.preventDefault();
    setDragging(false);
    const [file] = event.dataTransfer.files;
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    fileName.textContent = file.name;
  });
  fileInput.addEventListener('change', () => {
    fileName.textContent = fileInput.files[0]?.name ?? NO_FILE_LABEL;
  });
}

async function submitVerify(event, resultSlot) {
  event.preventDefault();
  const form = event.currentTarget;
  const file = form.elements.file.files[0];
  if (!file) {
    resultSlot.replaceChildren(alertBox('Choose a file to verify.'));
    return;
  }
  if (file.size > 20 * 1024 * 1024) {
    resultSlot.replaceChildren(alertBox('Choose a file no larger than 20 MB.'));
    return;
  }
  const submit = form.querySelector('button[type="submit"]');
  const keyInput = form.elements.api_key;
  const secret = keyInput.value;
  submit.disabled = true;
  resultSlot.replaceChildren(el('p', { text: 'Verifying...' }));
  try {
    const data = await fetchJson('/api/verify', { method: 'POST', body: new FormData(form) });
    const safeData = redactSecret(data, secret);
    resultSlot.replaceChildren(renderVerifyResult(safeData));
  } catch (error) {
    const message = secret ? error.message.split(secret).join(REDACTED) : error.message;
    resultSlot.replaceChildren(alertBox(`Verification failed: ${message}`));
  } finally {
    keyInput.value = '';
    submit.disabled = false;
  }
}

function renderVerifyResult(data) {
  const released = data.status === 'released';
  const doc = data.doc ?? {};
  return el('article', { className: 'result-card' }, [
    el('p', { className: `verdict ${released ? 'released' : 'refused'}`, text: released ? 'RELEASED' : 'REFUSED' }),
    ...renderRefusal(doc, released),
    ...(released ? [renderFacts(doc)] : []),
    renderOcr(data.ocr),
    renderRawJson(data),
  ]);
}

function renderRefusal(doc, released) {
  if (released) return [];
  const refusal = doc.error ?? doc.refusal ?? {};
  return [
    el('p', { className: 'refusal-code', text: `Refusal code: ${refusal.code ?? doc.refusal_code ?? 'unknown'}` }),
    el('p', { text: refusal.message ?? doc.refusal_message ?? 'No message given.' }),
  ];
}

function renderFacts(doc) {
  const batch = doc.data?.batches?.[0];
  const figures = {
    currency: batch?.currency,
    opening_balance: batch?.opening?.amount,
    closing_balance: batch?.closing?.amount,
    transaction_count: doc.data?.transactions?.length,
  };
  const items = FACT_FIELDS
    .filter(([, key]) => figures[key] !== undefined)
    .map(([label, key]) => el('div', { className: 'fact' }, [
      el('dt', { text: label }),
      el('dd', { text: formatValue(figures[key]) }),
    ]));
  return el('dl', { className: 'facts' }, items);
}

function renderOcr(ocr) {
  if (!ocr) return el('p', { text: 'No OCR engine was used.' });
  const engines = Array.isArray(ocr.engines) ? ocr.engines.join(', ') : formatValue(ocr.engines);
  const nodes = [el('p', { text: `OCR engines: ${engines}` })];
  if (ocr.fallback_used) {
    nodes.push(alertBox('Fallback OCR engine used. The primary engine did not run. Check the result before relying on it.', 'warning'));
  }
  return el('section', { className: 'ocr' }, nodes);
}

function renderRawJson(data) {
  return el('details', { className: 'raw' }, [
    el('summary', { text: 'Raw JSON' }),
    el('pre', { text: prettyJson(data) }),
  ]);
}

function prettyJson(data) {
  return redactText(JSON.stringify(data, null, 2));
}

async function renderResults() {
  return renderResultListing('Results', false);
}

async function renderBenchmarks() {
  return renderResultListing('Benchmarks', true);
}

async function renderResultListing(title, benchmarksOnly) {
  const listing = await fetchJson('/api/results');
  const allFiles = Array.isArray(listing.files) ? listing.files : [];
  const files = benchmarksOnly ? allFiles.filter(file => file.kind !== 'other') : allFiles;
  const detail = el('div', { className: 'result-detail', attrs: { 'aria-live': 'polite' } });
  return el('section', {}, [
    el('h2', { text: title }),
    ...(benchmarksOnly ? [el('p', { text: 'Browse saved benchmark results. Run benchmarks from the command line to create new results.' })] : []),
    files.length ? renderGroups(files, detail) : el('p', { text: 'No result files yet.' }),
    detail,
  ]);
}

function groupByKind(files) {
  const groups = new Map();
  for (const file of files) {
    const kind = file.kind ?? 'unknown';
    groups.set(kind, [...(groups.get(kind) ?? []), file]);
  }
  return groups;
}

function renderGroups(files, detail) {
  const groups = [...groupByKind(files)].map(([kind, group]) => el('div', { className: 'group' }, [
    el('h3', { text: kind }),
    el('ul', {}, group.map(file => el('li', {}, [renderFileButton(file, detail)]))),
  ]));
  return el('div', { className: 'groups' }, groups);
}

function renderFileButton(file, detail) {
  return el('button', {
    className: 'file-link',
    attrs: { type: 'button' },
    text: `${file.name} (${file.size ?? '?'} bytes)`,
    on: { click: () => openResult(file, detail) },
  });
}

function encodePath(name) {
  return name.split('/').map(encodeURIComponent).join('/');
}

async function openResult(file, detail) {
  const token = String(Number(detail.dataset.requestToken ?? 0) + 1);
  detail.dataset.requestToken = token;
  detail.replaceChildren(el('p', { text: `Loading ${file.name}...` }));
  try {
    const data = await fetchJson(`/api/results/${encodePath(file.name)}`);
    if (detail.dataset.requestToken !== token) return;
    const renderer = RESULT_RENDERERS[file.kind] ?? renderPrettyJson;
    detail.replaceChildren(el('h3', { text: file.name }), renderer(data));
  } catch (error) {
    if (detail.dataset.requestToken !== token) return;
    detail.replaceChildren(alertBox(`Could not load ${file.name}: ${error.message}`));
  }
}

function renderPrettyJson(data) {
  return el('pre', { className: 'json', text: prettyJson(data) });
}

function listOf(value) {
  if (Array.isArray(value)) return value;
  if (!isPlainObject(value)) return [];
  return Object.entries(value).map(([name, row]) => ({ name, ...(isPlainObject(row) ? row : { value: row }) }));
}

function orderColumns(items, priority) {
  const keys = [...new Set(items.flatMap(item => Object.keys(item)))];
  const first = priority.filter(key => keys.includes(key));
  return [...first, ...keys.filter(key => !first.includes(key))];
}

function headerLabel(column) {
  if (column === RISK_COLUMN) return 'WRONG RELEASES';
  return column.endsWith('_s') ? `${humanize(column.slice(0, -2))} (s)` : humanize(column);
}

function renderTable(rows, priority = []) {
  const items = rows.filter(isPlainObject);
  if (items.length === 0) return el('p', { text: 'None.' });
  const columns = orderColumns(items, priority);
  const head = el('tr', {}, columns.map(column => el('th', {
    text: headerLabel(column),
    className: column === RISK_COLUMN ? 'risk-col' : '',
    attrs: { scope: 'col' },
  })));
  const body = items.map(item => el('tr', {}, columns.map(column => el('td', {
    text: formatValue(item[column]),
    style: column === RISK_COLUMN && Number(item[column]) > 0 ? { color: '#b00020', fontWeight: '700' } : undefined,
  }))));
  return el('table', { className: 'data-table' }, [el('thead', {}, [head]), el('tbody', {}, body)]);
}

function renderOcrCompare(data) {
  if (!Array.isArray(data) && !isPlainObject(data)) return renderPrettyJson(data);
  const rows = listOf(Array.isArray(data) ? data : (data.rows ?? data.providers ?? []));
  const scored = rows.filter(row => row.status === 'ok');
  const skipped = rows.filter(row => row.status !== 'ok');
  const sections = [
    el('h3', { text: 'Provider scores' }),
    renderTable(scored, OCR_PRIORITY),
    el('h3', { text: 'Skipped providers' }),
    renderTable(skipped, ['provider_id', 'status', 'reason']),
  ];
  if (isPlainObject(data.observations)) {
    sections.push(el('h3', { text: 'Document observations' }));
    for (const [provider, observations] of Object.entries(data.observations)) {
      sections.push(el('h4', { text: provider }), renderTable(listOf(observations), ['name', 'status', 'code', 'pages', 'latencies_s', 'engines']));
    }
  }
  sections.push(renderRawJson(data));
  return el('div', { className: 'ocr-compare' }, sections);
}

function renderTokenCost(data) {
  if (!isPlainObject(data) || !Array.isArray(data.samples)) return renderTables(data);
  const measures = [data.tools, data.resources].filter(isPlainObject);
  const outcomes = [];
  for (const sample of data.samples.filter(isPlainObject)) {
    if (isPlainObject(sample.request)) measures.push(sample.request);
    if (isPlainObject(sample.response)) measures.push(sample.response);
    outcomes.push({
      filename: sample.filename, detail: sample.detail, status: sample.status, code: sample.code,
      response_bytes: sample.response?.raw_bytes, response_tokens: sample.response?.tokens,
    });
  }
  return el('div', {}, [
    el('p', { text: `Token method: ${formatValue(data.token_method)}` }),
    el('p', { text: 'Counts cover the measured serialized payloads; model prompts, completions and cache behavior are excluded.' }),
    el('h3', { text: 'Payload measurements' }),
    renderTable(measures, ['name', 'raw_bytes', 'tokens']),
    el('h3', { text: 'Sample outcomes' }),
    renderTable(outcomes, ['filename', 'detail', 'status', 'code', 'response_bytes', 'response_tokens']),
    renderRawJson(data),
  ]);
}

function renderTables(data) {
  if (Array.isArray(data)) return renderTable(data);
  if (!isPlainObject(data)) return renderPrettyJson(data);
  return el('div', {}, Object.entries(data).map(([key, value]) => el('section', {}, [
    el('h3', { text: humanize(key) }),
    renderValue(value),
  ])));
}

function renderValue(value) {
  if (Array.isArray(value)) return renderTable(value);
  if (isPlainObject(value)) return renderTable(listOf(value), ['name']);
  return el('p', { text: formatValue(value) });
}

async function renderSkills() {
  const skills = await fetchJson('/api/skills');
  const list = Array.isArray(skills) ? skills : [];
  return el('section', {}, [
    el('h2', { text: 'Skills' }),
    list.length
      ? el('div', { className: 'cards' }, list.map(renderSkillCard))
      : el('p', { text: 'No skills found.' }),
  ]);
}

function renderSkillCard(skill) {
  return el('article', { className: 'card' }, [
    el('h3', { text: skill.name }),
    el('p', { text: skill.description ?? '' }),
  ]);
}

function syncHash() {
  renderRoute();
}

window.addEventListener('hashchange', syncHash);
renderRoute();
