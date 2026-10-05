async function api(url, opts = {}) {
  const o = { headers: { 'Content-Type': 'application/json' }, ...opts };
  if (o.body && typeof o.body !== 'string') o.body = JSON.stringify(o.body);
  const r = await fetch(url, o);
  if (r.status === 401) { location.href = '/login'; return; }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Something went wrong.');
  return d;
}
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const peso = n => '₱' + Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const ago = d => { const t = new Date(); t.setDate(t.getDate() - d); return new Date(t - t.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const BADGE = { 'In Stock': 'green', 'Low Stock': 'amber', Critical: 'red', Borrowed: 'blue', Returned: 'green', Overdue: 'red', Pending: 'amber', Completed: 'green', Cancelled: 'gray', Regular: 'blue', Business: 'amber' };
const badge = s => `<span class="badge b-${BADGE[s] || 'gray'}">${esc(s)}</span>`;
const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const dt = s => s ? String(s).slice(0, 10) : '';

function toast(msg, bad) {
  const box = $('#toast'), d = document.createElement('div');
  d.textContent = msg; if (bad) d.className = 'bad'; box.appendChild(d);
  setTimeout(() => d.remove(), 3500);
}
function modal(html) {
  const o = document.createElement('div');
  o.className = 'overlay'; o.innerHTML = `<div class="modal" role="dialog">${html}</div>`;
  o.addEventListener('mousedown', e => { if (e.target === o) o.remove(); });
  document.body.appendChild(o);
  o.close = () => o.remove();
  const first = $('input,select', o); if (first) first.focus();
  return o;
}
function table(cols, rows, empty = 'Nothing to show yet.') {
  if (!rows.length) return `<div class="empty">${empty}</div>`;
  return `<div class="tablewrap"><table><thead><tr>${cols.map(c => `<th class="${c.num ? 'num' : ''}">${c.h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td class="${c.num ? 'num' : ''}">${c.f(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function customerForm(c, done) {
  c = c || { type: 'Regular' };
  const m = modal(`<h3>${c.id ? 'Edit customer' : 'Add customer'}</h3>
    <div class="f"><label>Name</label><input id="cf-name" value="${esc(c.name)}"></div>
    <div class="f"><label>Customer type</label><select id="cf-type"><option>Regular</option><option>Business</option></select></div>
    <div class="f"><label>Phone</label><input id="cf-phone" value="${esc(c.phone)}"></div>
    <div class="f"><label>Address</label><input id="cf-addr" value="${esc(c.address)}"></div>
    <div class="f"><label>Discount (%)</label><input id="cf-disc" type="number" min="0" max="100" step="0.5" value="${c.id ? c.discount_pct : ''}" placeholder="Blank = 0 for Regular, 5 for Business"></div>
    <div class="actions"><button class="btn ghost" id="cf-x">Cancel</button><button class="btn go" id="cf-ok">Save customer</button></div>`);
  $('#cf-type', m).value = c.type;
  $('#cf-x', m).onclick = m.close;
  $('#cf-ok', m).onclick = async () => {
    try {
      const body = { name: $('#cf-name', m).value, type: $('#cf-type', m).value, phone: $('#cf-phone', m).value, address: $('#cf-addr', m).value, discount_pct: $('#cf-disc', m).value };
      const r = c.id ? await api('/api/customers/' + c.id, { method: 'PUT', body }) : await api('/api/customers', { method: 'POST', body });
      m.close(); toast('Customer saved.'); done && done(r);
    } catch (e) { toast(e.message, true); }
  };
}
function tick() {
  const el = $('#clock'); if (!el) return;
  const n = new Date();
  el.textContent = n.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) + ' | ' + n.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  const h = n.getHours(), g = $('#greeting');
  if (g) g.textContent = (h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening') + ', ' + g.dataset.name + '!';
}
setInterval(tick, 30000); document.addEventListener('DOMContentLoaded', tick);
