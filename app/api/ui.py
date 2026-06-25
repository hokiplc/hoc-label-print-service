"""Minimal LAN admin UI: a single server-rendered HTML page with simple JS calling
the JSON API. No frontend framework, no build step."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>House of Coffee Label Printer</title>
<style>
body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #f7f5f2; color: #222; }
h1 { font-size: 1.3rem; }
section { background: white; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { text-align: left; padding: 0.4rem; border-bottom: 1px solid #eee; }
button { background: #3a2d1f; color: white; border: none; padding: 0.6rem 1rem; border-radius: 6px; font-size: 0.9rem; }
input { width: 100%; padding: 0.5rem; margin-bottom: 0.5rem; box-sizing: border-box; }
.status-completed { color: green; }
.status-failed { color: #b00020; }
.status-queued, .status-rendering, .status-printing { color: #a06a00; }
#apiKey { font-family: monospace; }
</style>
</head>
<body>
<h1>House of Coffee &mdash; Label Printer</h1>

<section>
<h2>API Key</h2>
<input id="apiKey" type="password" placeholder="X-API-Key">
</section>

<section>
<h2>Health</h2>
<pre id="health">loading...</pre>
<button onclick="refreshHealth()">Refresh</button>
<button onclick="testPrint()">Test print</button>
</section>

<section>
<h2>Recent jobs</h2>
<table id="jobsTable"><thead><tr><th>Created</th><th>Ref</th><th>Status</th><th>Error</th><th></th></tr></thead><tbody></tbody></table>
<button onclick="refreshJobs()">Refresh</button>
</section>

<script>
function apiKey() { return document.getElementById('apiKey').value; }

async function refreshHealth() {
  const res = await fetch('/health');
  document.getElementById('health').textContent = JSON.stringify(await res.json(), null, 2);
}

async function refreshJobs() {
  const res = await fetch('/jobs', { headers: { 'X-API-Key': apiKey() } });
  if (!res.ok) { alert('Failed to load jobs: ' + res.status); return; }
  const data = await res.json();
  const tbody = document.querySelector('#jobsTable tbody');
  tbody.innerHTML = '';
  for (const job of data.jobs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${job.created_at}</td><td>${job.job_ref || ''}</td>` +
      `<td class="status-${job.status}">${job.status}</td>` +
      `<td>${job.error_message || ''}</td>` +
      `<td><button onclick="reprint('${job.job_id}')">Reprint</button></td>`;
    tbody.appendChild(tr);
  }
}

async function reprint(jobId) {
  const res = await fetch(`/jobs/${jobId}/reprint`, { method: 'POST', headers: { 'X-API-Key': apiKey() } });
  if (!res.ok) { alert('Reprint failed: ' + res.status); return; }
  refreshJobs();
}

async function testPrint() {
  const res = await fetch('/admin/test-print', { method: 'POST', headers: { 'X-API-Key': apiKey() } });
  if (!res.ok) { alert('Test print failed: ' + res.status); return; }
  alert('Test print queued');
  refreshJobs();
}

refreshHealth();
refreshJobs();
setInterval(refreshHealth, 15000);
setInterval(refreshJobs, 15000);
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE
