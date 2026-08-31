/**
 * Coop Receipt Scraper Bookmarklet for Peng
 * 
 * Runs directly within the user's active session on https://medlem.coop.dk/ or https://prdmedlem.coop.dk/
 * Injects a floating modal, paginates through receipts API, fetches receipt details,
 * parses lines/discounts/totals, sends data directly to Peng API, and offers download backup.
 */

export function buildRawCoopBookmarkletJs(pengOrigin: string = '', inboundToken: string = ''): string {
  const ingestUrl = pengOrigin && inboundToken ? `${pengOrigin.replace(/\/$/, '')}/api/inbound/coop/${inboundToken}` : '';

  return `(function() {
  if (!window.location.hostname.includes('coop.dk')) {
    alert('Denne bookmarklet virker kun på medlem.coop.dk.\\n\\nLog venligst ind på https://medlem.coop.dk først.');
    return;
  }

  const EXISTING_MODAL = document.getElementById('peng-coop-modal');
  if (EXISTING_MODAL) EXISTING_MODAL.remove();

  const PENG_INGEST_URL = ${JSON.stringify(ingestUrl)};

  // Create UI Container
  const container = document.createElement('div');
  container.id = 'peng-coop-modal';
  container.style.cssText = 'position:fixed;top:24px;right:24px;width:380px;background:#1e293b;color:#f8fafc;padding:24px;border-radius:16px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);z-index:9999999;font-family:system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.5;border:1px solid #334155;';

  container.innerHTML = \`
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-size:24px;">🧾</span>
        <h3 style="margin:0;font-size:16px;font-weight:600;color:#38bdf8;">Peng Coop Henter</h3>
      </div>
      <button id="peng-close-btn" style="background:none;border:none;color:#94a3b8;font-size:20px;cursor:pointer;padding:4px;">✕</button>
    </div>
    
    <div id="peng-body">
      <p style="margin:0 0 14px 0;color:#cbd5e1;font-size:13px;">Henter dine Coop-kvitteringer og synkroniserer dem \${PENG_INGEST_URL ? 'automatisk direkte til Peng' : 'til en fil'}.</p>
      
      <div style="margin-bottom:16px;">
        <label style="display:block;margin-bottom:6px;font-size:12px;font-weight:500;color:#94a3b8;">Tidsperiode:</label>
        <select id="peng-range-select" style="width:100%;padding:8px 12px;border-radius:8px;background:#0f172a;border:1px solid #334155;color:#f8fafc;font-size:13px;outline:none;">
          <option value="all">Alle kvitteringer (fuld historik)</option>
          <option value="90">Seneste 3 måneder (90 dage)</option>
          <option value="30">Seneste 30 dage</option>
        </select>
      </div>

      <div style="display:flex;gap:10px;">
        <button id="peng-start-btn" style="flex:1;padding:10px 16px;background:#0284c7;color:#fff;border:none;border-radius:8px;font-weight:600;cursor:pointer;transition:background 0.2s;">Start Hentning & Synk</button>
      </div>
    </div>

    <div id="peng-progress-section" style="display:none;">
      <div style="margin-bottom:8px;display:flex;justify-content:space-between;font-size:12px;">
        <span id="peng-status-text" style="color:#38bdf8;font-weight:500;">Henter kvitteringsliste...</span>
        <span id="peng-progress-percent" style="color:#94a3b8;">0%</span>
      </div>
      <div style="width:100%;height:8px;background:#0f172a;border-radius:4px;overflow:hidden;margin-bottom:12px;">
        <div id="peng-progress-bar" style="width:0%;height:100%;background:#38bdf8;transition:width 0.2s;"></div>
      </div>
      <p id="peng-details-text" style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">Forbereder...</p>
    </div>

    <div id="peng-complete-section" style="display:none;">
      <div style="background:#0f172a;padding:12px;border-radius:8px;border:1px solid #334155;margin-bottom:16px;">
        <p style="margin:0 0 6px 0;color:#4ade80;font-weight:600;font-size:13px;">✓ Hentning fuldført!</p>
        <p id="peng-summary-text" style="margin:0;color:#cbd5e1;font-size:12px;">0 kvitteringer behandlet.</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <button id="peng-redownload-btn" style="width:100%;padding:8px;background:#0284c7;color:#fff;border:none;border-radius:8px;font-weight:600;cursor:pointer;">Gem kopi som JSON</button>
        <button id="peng-copy-btn" style="width:100%;padding:8px;background:#334155;color:#f8fafc;border:none;border-radius:8px;font-weight:500;cursor:pointer;">Kopier JSON til udklipsholder</button>
      </div>
    </div>
  \`;

  document.body.appendChild(container);

  const closeBtn = document.getElementById('peng-close-btn');
  const startBtn = document.getElementById('peng-start-btn');
  const bodyDiv = document.getElementById('peng-body');
  const progressDiv = document.getElementById('peng-progress-section');
  const completeDiv = document.getElementById('peng-complete-section');
  const statusText = document.getElementById('peng-status-text');
  const percentText = document.getElementById('peng-progress-percent');
  const progressBar = document.getElementById('peng-progress-bar');
  const detailsText = document.getElementById('peng-details-text');
  const summaryText = document.getElementById('peng-summary-text');
  const redownloadBtn = document.getElementById('peng-redownload-btn');
  const copyBtn = document.getElementById('peng-copy-btn');
  const rangeSelect = document.getElementById('peng-range-select');

  closeBtn.onclick = () => container.remove();

  let isAborted = false;
  let finalJsonString = '';

  const parseAmount = (str) => {
    if (!str) return null;
    const cleaned = str.replace(/\\s/g, '').replace(/\\./g, '').replace(',', '.');
    const val = parseFloat(cleaned);
    return isNaN(val) ? null : val;
  };

  const parseHtmlReceipt = (htmlString, summaryItem) => {
    let rawHtml = htmlString;
    if (typeof rawHtml === 'string' && rawHtml.startsWith('"') && rawHtml.endsWith('"')) {
      try {
        rawHtml = JSON.parse(rawHtml);
      } catch (e) {}
    }
    const parser = new DOMParser();
    const doc = parser.parseFromString(rawHtml, 'text/html');
    const lines = [];

    const rows = Array.from(doc.querySelectorAll('table tr'));
    for (const row of rows) {
      const cells = Array.from(row.querySelectorAll('td'));
      if (cells.length < 2) continue;

      const firstCellText = (cells[0].textContent || '').trim().replace(/\\s+/g, ' ');
      const secondCellText = (cells[1].textContent || '').trim().replace(/\\s+/g, ' ');

      if (
        firstCellText === "Rabat på køb" || 
        firstCellText === "Bonus på køb" || 
        row.classList.contains('bonus-row') ||
        row.classList.contains('expandable-bonus-row') ||
        row.classList.contains('expanded-bonus-text-row') ||
        row.classList.contains('expand-btn')
      ) {
        continue;
      }

      if (
        firstCellText === "Coop-betaling" || 
        firstCellText.toLowerCase().includes('betaling') ||
        firstCellText.toLowerCase().includes('dankort') ||
        firstCellText.toLowerCase().includes('mastercard') ||
        firstCellText.toLowerCase().includes('visa')
      ) {
        break;
      }

      const priceVal = parseAmount(secondCellText);
      if (firstCellText && priceVal !== null) {
        lines.push({
          name: firstCellText,
          price: priceVal.toFixed(2)
        });
      }
    }

    const dateStr = summaryItem.localPurchaseTimestamp ? summaryItem.localPurchaseTimestamp.slice(0, 10) : '';
    const totalVal = summaryItem.totalAmount && typeof summaryItem.totalAmount.value === 'number' 
      ? summaryItem.totalAmount.value.toFixed(2) 
      : '0.00';

    return {
      receiptId: String(summaryItem.receiptId),
      storeName: summaryItem.storeName || 'Coop',
      purchaseDate: dateStr,
      purchaseDateTime: summaryItem.localPurchaseTimestamp || dateStr,
      totalPrice: totalVal,
      currency: (summaryItem.totalAmount && summaryItem.totalAmount.currency) || 'DKK',
      lines: lines
    };
  };

  const triggerDownload = (jsonStr) => {
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(jsonStr);
    const a = document.createElement('a');
    a.setAttribute('href', dataUri);
    a.setAttribute('download', 'coop-receipts.json');
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
    }, 300);
  };

  startBtn.onclick = async () => {
    bodyDiv.style.display = 'none';
    progressDiv.style.display = 'block';

    const rangeDays = rangeSelect.value === 'all' ? Infinity : parseInt(rangeSelect.value, 10);
    const cutoffDate = rangeDays === Infinity ? null : new Date(Date.now() - rangeDays * 86400000);

    let allSummaries = [];
    let cursor = null;
    let keepFetchingList = true;

    try {
      // 1. Fetch List
      while (keepFetchingList && !isAborted) {
        statusText.textContent = \`Henter liste (\${allSummaries.length} fundet)...\`;
        const url = \`https://medlem.coop.dk/umbraco/api/receiptsapi/get?limit=25\${cursor ? '&cursor=' + encodeURIComponent(cursor) : ''}\`;
        const res = await fetch(url, { credentials: 'include' });
        if (!res.ok) throw new Error('Kunne ikke hente kvitteringsliste (' + res.status + ')');
        const data = await res.json();
        const batch = data.receipts || [];
        if (batch.length === 0) break;

        for (const item of batch) {
          if (cutoffDate && item.localPurchaseTimestamp) {
            const pDate = new Date(item.localPurchaseTimestamp);
            if (pDate < cutoffDate) {
              keepFetchingList = false;
              break;
            }
          }
          allSummaries.push(item);
        }

        cursor = data.nextCursor;
        if (!cursor) break;
        await new Promise(r => setTimeout(r, 100));
      }

      if (allSummaries.length === 0) {
        alert('Ingen kvitteringer fundet i den valgte periode.');
        container.remove();
        return;
      }

      // 2. Batch Fetch Details
      statusText.textContent = 'Henter kvitteringsdetaljer...';
      const results = [];
      const CONCURRENCY = 4;
      let completedCount = 0;

      for (let i = 0; i < allSummaries.length; i += CONCURRENCY) {
        if (isAborted) break;
        const chunk = allSummaries.slice(i, i + CONCURRENCY);
        
        const chunkResults = await Promise.all(chunk.map(async (summary) => {
          try {
            const detailUrl = \`https://medlem.coop.dk/umbraco/api/receiptsapi/getdetails?id=\${encodeURIComponent(summary.receiptId)}\`;
            const dRes = await fetch(detailUrl, { credentials: 'include' });
            if (!dRes.ok) return null;
            const html = await dRes.text();
            return parseHtmlReceipt(html, summary);
          } catch (e) {
            console.error('Fejl ved hentning af kvittering', summary.receiptId, e);
            return null;
          }
        }));

        for (const r of chunkResults) {
          if (r) results.push(r);
        }

        completedCount += chunk.length;
        const pct = Math.min(100, Math.round((completedCount / allSummaries.length) * 100));
        progressBar.style.width = pct + '%';
        percentText.textContent = pct + '%';
        detailsText.textContent = \`\${completedCount} / \${allSummaries.length} kvitteringer\`;

        await new Promise(r => setTimeout(r, 150));
      }

      finalJsonString = JSON.stringify(results, null, 2);

      // 3. Direct Ingestion to Peng API if configured
      let directSyncOk = false;
      if (PENG_INGEST_URL) {
        statusText.textContent = 'Sender kvitteringer direkte til Peng...';
        try {
          const ingestRes = await fetch(PENG_INGEST_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: finalJsonString
          });
          if (ingestRes.ok) {
            directSyncOk = true;
          }
        } catch (e) {
          console.warn('Direct push to Peng failed, falling back to download', e);
        }
      }

      if (!directSyncOk) {
        triggerDownload(finalJsonString);
      }

      progressDiv.style.display = 'none';
      completeDiv.style.display = 'block';

      if (directSyncOk) {
        summaryText.innerHTML = \`✓ <b>\${results.length}</b> kvitteringer er automatisk sendt og indlæst i Peng!\`;
      } else {
        summaryText.innerHTML = \`<b>\${results.length}</b> kvitteringer er hentet og gemt i <b>coop-receipts.json</b>.\`;
      }

      redownloadBtn.onclick = () => triggerDownload(finalJsonString);
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(finalJsonString);
          copyBtn.textContent = '✓ Kopieret til udklipsholder!';
          setTimeout(() => { copyBtn.textContent = 'Kopier JSON til udklipsholder'; }, 2000);
        } catch (err) {
          alert('Kunne ikke kopiere automatisk.');
        }
      };

    } catch (err) {
      console.error('Fejl under hentning:', err);
      alert('Der opstod en fejl: ' + err.message);
      container.remove();
    }
  };
})();`;
}

export function buildCoopBookmarkletHref(pengOrigin: string = '', inboundToken: string = ''): string {
  return `javascript:${encodeURIComponent(buildRawCoopBookmarkletJs(pengOrigin, inboundToken))}`;
}

export const RAW_COOP_BOOKMARKLET_JS = buildRawCoopBookmarkletJs();
export const COOP_BOOKMARKLET_HREF = buildCoopBookmarkletHref();
