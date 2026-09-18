const ui = {
  apiBase: document.querySelector('#apiBase'), sampleSelect: document.querySelector('#sampleSelect'),
  loadSample: document.querySelector('#loadSample'), payload: document.querySelector('#payloadEditor'),
  run: document.querySelector('#runOptimization'), checkHealth: document.querySelector('#checkHealth'),
  status: document.querySelector('#systemStatus'), statusText: document.querySelector('#statusText'),
  payloadState: document.querySelector('#payloadState'), charCount: document.querySelector('#charCount'),
  scenarioTitle: document.querySelector('#scenarioTitle'), resultSource: document.querySelector('#resultSource'),
  totalCost: document.querySelector('#totalCost'), totalGrid: document.querySelector('#totalGrid'),
  peakGrid: document.querySelector('#peakGrid'), batteryReturn: document.querySelector('#batteryReturn'),
  chart: document.querySelector('#dispatchChart'), directives: document.querySelector('#directiveList'),
  directiveCount: document.querySelector('#directiveCount'), validation: document.querySelector('#validationList'),
  scheduleBody: document.querySelector('#scheduleBody'), download: document.querySelector('#downloadResult'),
  resultsPanel: document.querySelector('.results-panel'), toast: document.querySelector('#toast')
};

let cases = [];
let currentRequest = null;
let currentResult = null;

const number = (value, digits = 1) => new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(Number(value));
const esc = value => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const endpoint = path => `${ui.apiBase.value.trim().replace(/\/$/, '')}${path}`;

function toast(message, error = false) {
  ui.toast.textContent = message;
  ui.toast.className = `toast show${error ? ' error' : ''}`;
  window.setTimeout(() => ui.toast.className = 'toast', 3200);
}

function setHealth(ok, label) {
  ui.status.classList.toggle('online', ok);
  ui.status.classList.toggle('offline', !ok);
  ui.statusText.textContent = label;
}

async function checkHealth() {
  setHealth(false, 'Checking optimizer');
  try {
    const response = await fetch(endpoint('/health'), { signal: AbortSignal.timeout(5000) });
    const body = await response.json();
    if (!response.ok || body.status !== 'ok') throw new Error('Unexpected health response');
    setHealth(true, 'Optimizer online');
    return true;
  } catch (_) {
    setHealth(false, ui.apiBase.value.trim() ? 'API unreachable' : 'Preview mode');
    return false;
  }
}

async function loadCasePack() {
  try {
    const response = await fetch('/web/data/cases.json');
    if (!response.ok) throw new Error('Sample pack unavailable');
    const pack = await response.json();
    cases = pack.cases || [];
    ui.sampleSelect.innerHTML = cases.map((item, index) => `<option value="${index}">${esc(item.id)} · ${esc(item.label)}</option>`).join('');
    if (cases.length) loadSelectedCase();
  } catch (error) {
    ui.sampleSelect.innerHTML = '<option>Sample pack unavailable</option>';
    ui.payloadState.textContent = error.message;
    ui.payloadState.className = 'invalid';
  }
}

function loadSelectedCase() {
  const selected = cases[Number(ui.sampleSelect.value) || 0];
  if (!selected) return;
  currentRequest = selected.input;
  ui.payload.value = JSON.stringify(selected.input, null, 2);
  updatePayloadState();
  renderResult(selected.expected_output, selected.input, 'Reference preview');
  toast(`${selected.id} loaded`);
}

function updatePayloadState() {
  ui.charCount.textContent = `${ui.payload.value.length.toLocaleString()} chars`;
  try {
    currentRequest = JSON.parse(ui.payload.value);
    ui.payloadState.textContent = 'Valid JSON';
    ui.payloadState.className = 'valid';
  } catch (_) {
    ui.payloadState.textContent = 'Invalid JSON';
    ui.payloadState.className = 'invalid';
  }
}

async function runOptimization() {
  let request;
  try { request = JSON.parse(ui.payload.value); }
  catch (_) { toast('Fix the request JSON before running.', true); return; }
  currentRequest = request;
  ui.run.disabled = true;
  ui.run.querySelector('span').textContent = 'Optimizing…';
  ui.resultsPanel.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(endpoint('/optimize-energy'), {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(request)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || result.error || `HTTP ${response.status}`);
    renderResult(result, request, 'Live API result');
    setHealth(true, 'Optimizer online');
    toast('Optimization completed and replay-checked.');
  } catch (error) {
    toast(`Optimization failed: ${typeof error.message === 'string' ? error.message : 'unknown error'}`, true);
    setHealth(false, 'API needs attention');
  } finally {
    ui.run.disabled = false;
    ui.run.querySelector('span').textContent = 'Run optimization';
    ui.resultsPanel.setAttribute('aria-busy', 'false');
  }
}

function renderResult(result, request, source) {
  currentResult = result;
  ui.scenarioTitle.textContent = result.scenario_id || request.scenario_id || 'Scenario result';
  ui.resultSource.textContent = source;
  ui.totalCost.textContent = number(result.total_cost_bdt, 2);
  ui.totalGrid.textContent = number(result.total_grid_kwh, 2);
  ui.peakGrid.textContent = number(result.peak_grid_kwh, 2);
  const lastEnergy = result.hourly_plan?.[23]?.battery_energy_after_kwh;
  const initial = request.battery?.initial_energy_kwh;
  ui.batteryReturn.textContent = Math.abs(Number(lastEnergy) - Number(initial)) <= .01 ? 'PASS' : 'FAIL';
  ui.batteryReturn.style.color = ui.batteryReturn.textContent === 'PASS' ? 'var(--lime)' : 'var(--danger)';
  renderChart(result.hourly_plan || []);
  renderDirectives(result.directive_interpretation || []);
  renderTable(result.hourly_plan || []);
  renderValidation(validateResult(request, result));
  ui.download.disabled = false;
}

function renderChart(plan) {
  if (plan.length !== 24) { ui.chart.innerHTML = '<div class="empty-state">A complete 24-hour plan is required.</div>'; return; }
  const width = 1100, height = 290, left = 38, right = 16, top = 18, bottom = 34;
  const plotW = width - left - right, plotH = height - top - bottom;
  const peak = Math.max(1, ...plan.flatMap(row => [Number(row.grid_kwh), Number(row.solar_used_kwh), Number(row.battery_energy_after_kwh)]));
  const x = index => left + (index + .5) * plotW / 24;
  const y = value => top + plotH - Number(value) / peak * plotH;
  const barW = Math.max(4, plotW / 24 * .3);
  const gridLines = [0,.25,.5,.75,1].map(t => {
    const yy = top + plotH * (1-t);
    return `<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="#1e2b35"/><text x="${left-8}" y="${yy+4}" text-anchor="end" fill="#64717a" font-size="10">${number(peak*t,0)}</text>`;
  }).join('');
  const bars = plan.map((row, i) => {
    const gy = y(row.grid_kwh), sy = y(row.solar_used_kwh);
    return `<rect x="${x(i)-barW-1}" y="${gy}" width="${barW}" height="${top+plotH-gy}" fill="#d5ff40" opacity=".78"/><rect x="${x(i)+1}" y="${sy}" width="${barW}" height="${top+plotH-sy}" fill="#4be5e0" opacity=".78"/>`;
  }).join('');
  const points = plan.map((row, i) => `${x(i)},${y(row.battery_energy_after_kwh)}`).join(' ');
  const labels = plan.filter((_,i)=>i%3===0 || i===23).map((row,i0) => {
    const i = row.hour;
    return `<text x="${x(i)}" y="${height-10}" text-anchor="middle" fill="#64717a" font-size="10">${String(i).padStart(2,'0')}</text>`;
  }).join('');
  ui.chart.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">${gridLines}${bars}<polyline points="${points}" fill="none" stroke="#ff8a4c" stroke-width="2.5" vector-effect="non-scaling-stroke"/>${plan.map((row,i)=>`<circle cx="${x(i)}" cy="${y(row.battery_energy_after_kwh)}" r="2.8" fill="#ff8a4c"/>`).join('')}${labels}</svg>`;
}

function renderDirectives(items) {
  ui.directiveCount.textContent = items.length;
  if (!items.length) { ui.directives.innerHTML = '<div class="empty-state compact">No interpretations returned.</div>'; return; }
  ui.directives.innerHTML = items.map(item => `
    <div class="directive">
      <span class="directive-index">N${Number(item.note_index)+1}</span>
      <div><strong>${esc(item.directive_type)}</strong><p>${esc(item.explanation)}</p></div>
      <code>${item.structured_adjustment ? esc(JSON.stringify(item.structured_adjustment)) : 'no_op'}</code>
    </div>`).join('');
}

function renderTable(plan) {
  if (!plan.length) { ui.scheduleBody.innerHTML = '<tr><td colspan="6" class="empty-cell">No schedule available.</td></tr>'; return; }
  ui.scheduleBody.innerHTML = plan.map(row => `<tr>
    <td>${String(row.hour).padStart(2,'0')}:00</td><td>${number(row.grid_kwh,3)}</td><td>${number(row.solar_used_kwh,3)}</td>
    <td><span class="action-chip ${esc(row.battery_action)}">${esc(row.battery_action)}</span></td>
    <td>${number(row.battery_kwh,3)}</td><td>${number(row.battery_energy_after_kwh,3)}</td>
  </tr>`).join('');
}

function effectiveLimits(request, directives) {
  const solar = request.hours.slice().sort((a,b)=>a.hour-b.hour).map(row => Number(row.solar_kwh));
  const reserve = Array(24).fill(Number(request.battery.minimum_energy_kwh));
  const charge = Array(24).fill(Number(request.battery.max_charge_kwh_per_hour));
  const discharge = Array(24).fill(Number(request.battery.max_discharge_kwh_per_hour));
  const grid = Array(24).fill(Infinity);
  for (const directive of directives || []) {
    if (!directive.applies || !directive.structured_adjustment) continue;
    const adj = directive.structured_adjustment, hours = adj.hours || [];
    for (const hour of hours) {
      if (directive.directive_type === 'solar_reduction') solar[hour] *= Number(adj.factor);
      if (directive.directive_type === 'minimum_battery_reserve') reserve[hour] = Math.max(reserve[hour], Number(adj.minimum_energy_kwh));
      if (directive.directive_type === 'no_charge_window') charge[hour] = 0;
      if (directive.directive_type === 'no_discharge_window') discharge[hour] = 0;
      if (directive.directive_type === 'max_grid_window') grid[hour] = Math.min(grid[hour], Number(adj.max_grid_kwh));
    }
  }
  return {solar,reserve,charge,discharge,grid};
}

function validateResult(request, result) {
  const checks = [];
  const plan = result.hourly_plan || [], directives = result.directive_interpretation || [];
  checks.push({ok: directives.length === request.operator_notes.length && directives.every((d,i)=>d.note_index===i), label:'One ordered interpretation per note'});
  checks.push({ok: plan.length === 24 && new Set(plan.map(row=>row.hour)).size===24, label:'24 unique schedule hours'});
  if (plan.length !== 24) return checks;
  const hours = request.hours.slice().sort((a,b)=>a.hour-b.hour), limits = effectiveLimits(request,directives), tol=.011;
  let previous = Number(request.battery.initial_energy_kwh), balance=true, solar=true, battery=true, directive=true;
  for (let h=0; h<24; h++) {
    const row=plan[h], source=hours[h], amount=Number(row.battery_kwh), charging=row.battery_action==='charge'?amount:0, discharging=row.battery_action==='discharge'?amount:0;
    balance &&= Math.abs(Number(row.grid_kwh)+Number(row.solar_used_kwh)+discharging-Number(source.demand_kwh)-charging) <= tol;
    solar &&= Number(row.solar_used_kwh) >= -tol && Number(row.solar_used_kwh) <= limits.solar[h]+tol;
    battery &&= Math.abs(Number(row.battery_energy_after_kwh)-(previous+charging-discharging))<=tol && Number(row.battery_energy_after_kwh)>=limits.reserve[h]-tol && Number(row.battery_energy_after_kwh)<=Number(request.battery.capacity_kwh)+tol;
    directive &&= charging<=limits.charge[h]+tol && discharging<=limits.discharge[h]+tol && Number(row.grid_kwh)<=limits.grid[h]+tol;
    previous=Number(row.battery_energy_after_kwh);
  }
  checks.push({ok:balance,label:'Hourly energy balance'});
  checks.push({ok:solar,label:'Effective solar limits'});
  checks.push({ok:battery,label:'Battery state, bounds, and rates'});
  checks.push({ok:directive,label:'Directive windows and grid caps'});
  checks.push({ok:Math.abs(previous-Number(request.battery.initial_energy_kwh))<=tol,label:'End-of-day battery neutrality'});
  const totalGrid=plan.reduce((s,r)=>s+Number(r.grid_kwh),0), totalCost=plan.reduce((s,r,i)=>s+Number(r.grid_kwh)*Number(hours[i].tariff_bdt_per_kwh),0), peak=Math.max(...plan.map(r=>Number(r.grid_kwh)));
  checks.push({ok:Math.abs(totalGrid-Number(result.total_grid_kwh))<=tol && Math.abs(totalCost-Number(result.total_cost_bdt))<=tol && Math.abs(peak-Number(result.peak_grid_kwh))<=tol,label:'Reported totals match the plan'});
  return checks;
}

function renderValidation(checks) {
  ui.validation.innerHTML = checks.map(check => `<li class="${check.ok?'':'fail'}"><span>${check.ok?'✓':'×'}</span>${esc(check.label)}</li>`).join('');
}

function downloadResult() {
  if (!currentResult) return;
  const blob = new Blob([JSON.stringify(currentResult,null,2)], {type:'application/json'});
  const link = document.createElement('a'); link.href=URL.createObjectURL(blob); link.download=`${currentResult.scenario_id || 'gridwise'}-result.json`; link.click(); URL.revokeObjectURL(link.href);
}

ui.loadSample.addEventListener('click', loadSelectedCase);
ui.sampleSelect.addEventListener('change', loadSelectedCase);
ui.payload.addEventListener('input', updatePayloadState);
ui.run.addEventListener('click', runOptimization);
ui.checkHealth.addEventListener('click', checkHealth);
ui.download.addEventListener('click', downloadResult);
ui.apiBase.addEventListener('change', checkHealth);

loadCasePack();
checkHealth();
