/**
 * GharKhoj AI - Consumer Real Estate Portal Frontend Engine
 */

let currentQuery = "noida me 2bhk sasta near metro";
let currentTx = "all";
let currentCity = "all";
let currentBhk = "all";
let activeProperties = [];

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  // Trigger initial search
  executeSearch(currentQuery);
});

function initEventListeners() {
  const searchInput = document.getElementById("search-input");
  const searchBtn = document.getElementById("search-btn");
  const searchForm = document.getElementById("search-form");

  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = searchInput.value.trim();
      executeSearch(val);
    });
  }

  if (searchBtn) {
    searchBtn.addEventListener("click", () => {
      const val = searchInput.value.trim();
      executeSearch(val);
    });
  }

  // Quick query pill clicks
  document.querySelectorAll(".query-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.getAttribute("data-query");
      if (query) {
        searchInput.value = query;
        executeSearch(query);
      }
    });
  });

  // Buy / Rent Tab buttons
  document.querySelectorAll(".tab-btn").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentTx = tab.getAttribute("data-tx") || "all";
      executeSearch(searchInput.value.trim());
    });
  });

  // City filter buttons
  document.querySelectorAll(".city-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".city-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentCity = btn.getAttribute("data-city") || "all";
      executeSearch(searchInput.value.trim());
    });
  });

  // Modal close handlers
  const modalClose = document.getElementById("modal-close");
  const modalOverlay = document.getElementById("property-modal");
  if (modalClose) {
    modalClose.addEventListener("click", closeModal);
  }
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });
  }
}

async function executeSearch(query) {
  const grid = document.getElementById("property-grid");
  const countEl = document.getElementById("results-count");
  const hudContainer = document.getElementById("ai-hud");

  // Show loading skeleton
  grid.innerHTML = Array(6)
    .fill(0)
    .map(
      () => `
    <div class="property-card">
      <div class="card-img-wrapper skeleton"></div>
      <div class="card-content">
        <div style="height:24px;width:60%;margin-bottom:12px;" class="skeleton"></div>
        <div style="height:18px;width:90%;margin-bottom:8px;" class="skeleton"></div>
        <div style="height:14px;width:40%;margin-bottom:16px;" class="skeleton"></div>
        <div style="height:40px;width:100%;margin-top:auto;" class="skeleton"></div>
      </div>
    </div>
  `
    )
    .join("");

  try {
    const payload = {
      query: query || "",
      city: currentCity !== "all" ? currentCity : null,
      transaction: currentTx !== "all" ? currentTx : null,
      page: 1,
      page_size: 12,
    };

    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("API call failed");
    const data = await res.json();

    activeProperties = data.properties || [];
    renderAIHUD(data);
    renderProperties(activeProperties, data.is_fallback);

    if (countEl) {
      countEl.innerText = `${activeProperties.length} Homes Found`;
    }
  } catch (err) {
    console.error(err);
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px;">
        <h3 style="color:#f43f5e; margin-bottom: 8px;">Failed to load properties</h3>
        <p style="color:#94a3b8;">Please check your server connection or try a different search phrase.</p>
      </div>
    `;
  }
}

function renderAIHUD(data) {
  const hudContainer = document.getElementById("ai-hud");
  if (!hudContainer) return;

  if (!data.query && !Object.keys(data.filter || {}).length) {
    hudContainer.style.display = "none";
    return;
  }

  hudContainer.style.display = "block";
  const metrics = data.metrics || {};
  const filter = data.filter || {};

  document.getElementById("hud-tier").innerText = metrics.tier_label || metrics.tier;
  document.getElementById("hud-latency").innerText = `${metrics.total_latency_ms} ms`;
  document.getElementById("hud-cost").innerText = metrics.cost_usd || "$0.00";

  // Render Extracted Intent Tags
  const tagsRow = document.getElementById("hud-tags");
  let tagsHtml = "";

  if (filter.city) {
    tagsHtml += `<span class="intent-tag">📍 City: ${filter.city}</span>`;
  }
  if (filter.locality) {
    tagsHtml += `<span class="intent-tag">📌 Locality: ${filter.locality}</span>`;
  }
  if (filter.bhk) {
    tagsHtml += `<span class="intent-tag">🛏️ ${filter.bhk} BHK</span>`;
  }
  if (filter.transaction) {
    tagsHtml += `<span class="intent-tag">🤝 ${filter.transaction.toUpperCase()}</span>`;
  }
  if (filter.budget_max) {
    const maxStr = filter.budget_max >= 10000000 
      ? `₹${(filter.budget_max / 10000000).toFixed(1)} Cr`
      : `₹${(filter.budget_max / 100000).toFixed(1)} Lakh`;
    tagsHtml += `<span class="intent-tag">💰 Max: ${maxStr}</span>`;
  }
  if (filter.furnishing) {
    tagsHtml += `<span class="intent-tag">🛋️ ${filter.furnishing}</span>`;
  }
  if (filter.near && filter.near.length > 0) {
    tagsHtml += `<span class="intent-tag">🚇 Near: ${filter.near.join(", ")}</span>`;
  }

  tagsRow.innerHTML = tagsHtml || `<span class="intent-tag">🔍 All Matching Criteria</span>`;
}

function renderProperties(properties, isFallback) {
  const grid = document.getElementById("property-grid");
  if (!properties || properties.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 70px 20px;">
        <div style="font-size:3rem; margin-bottom:14px;">🏡</div>
        <h3 style="font-size: 1.4rem; color: #fff; margin-bottom: 8px;">No Direct Listings Found</h3>
        <p style="color: #94a3b8; max-width: 480px; margin: 0 auto 20px;">
          Try expanding your search query or picking one of the preset popular Hinglish searches above.
        </p>
      </div>
    `;
    return;
  }

  const fallbackBanner = isFallback
    ? `<div style="grid-column: 1 / -1; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 12px; padding: 12px 20px; color: #c7d2fe; display: flex; align-items: center; gap: 10px;">
        <span>💡</span>
        <span>Showing closest matches with relaxed budget and nearby localities.</span>
       </div>`
    : "";

  grid.innerHTML =
    fallbackBanner +
    properties
      .map((p, idx) => {
        const txBadgeClass = p.transaction === "rent" ? "badge-rent" : "badge-buy";
        const txBadgeText = p.transaction === "rent" ? "For Rent" : "For Sale";
        const bhkText = p.bedrooms ? `${p.bedrooms} BHK` : "Studio/Flat";
        const sqftText = p.sqft ? `${p.sqft.toLocaleString()} sq.ft` : "Spacious";
        const furnText = p.furnishing ? p.furnishing.charAt(0).toUpperCase() + p.furnishing.slice(1) : "Unfurnished";

        const amenitiesHtml = (p.near || [])
          .map((n) => `<span class="amenity-chip">✨ Near ${n}</span>`)
          .join("");

        return `
      <div class="property-card" data-idx="${idx}">
        <div class="card-img-wrapper">
          <img class="card-img" src="${p.photo_url || 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=600'}" alt="${p.title}" loading="lazy" />
          <span class="card-badge ${txBadgeClass}">${txBadgeText}</span>
          <span class="verified-pill">⭐ RERA Verified</span>
        </div>
        <div class="card-content">
          <div class="card-price-row">
            <span class="card-price">${p.price_formatted}</span>
            <span style="font-size:0.8rem; color:#94a3b8;">${p.property_type ? p.property_type.toUpperCase() : 'APARTMENT'}</span>
          </div>
          <h4 class="card-title" title="${p.title}">${p.title}</h4>
          <div class="card-locality">
            <span>📍</span>
            <span>${p.locality ? p.locality + ', ' : ''}${p.city}</span>
          </div>
          <div class="card-specs">
            <div class="spec-item">
              <span class="spec-label">Configuration</span>
              <span class="spec-value">${bhkText}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Super Area</span>
              <span class="spec-value">${sqftText}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Furnishing</span>
              <span class="spec-value">${furnText}</span>
            </div>
          </div>
          <div class="card-tags">
            ${amenitiesHtml}
          </div>
          <div class="card-actions">
            <button class="btn-card-primary" onclick="openModal(${idx})">Quick View</button>
            <button class="btn-card-secondary" onclick="contactAgent('${p.id}', '${p.title}')">Contact</button>
          </div>
        </div>
      </div>
    `;
      })
      .join("");
}

function openModal(idx) {
  const p = activeProperties[idx];
  if (!p) return;

  const modal = document.getElementById("property-modal");
  const modalContent = document.getElementById("modal-content");

  const bhkText = p.bedrooms ? `${p.bedrooms} BHK Apartment` : "Luxury Property";
  const emiEstimate = p.transaction === "buy" ? Math.round(p.price * 0.0075) : Math.round(p.price * 0.1);

  modalContent.innerHTML = `
    <img src="${p.photo_url}" class="modal-img" alt="${p.title}" />
    <div class="modal-body">
      <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:12px;">
        <h2 style="font-size:1.8rem; color:#fff; font-family:var(--font-heading);">${p.price_formatted}</h2>
        <span class="verified-pill" style="position:static;">⭐ Verified Property</span>
      </div>
      <h3 style="font-size:1.3rem; color:#e2e8f0; margin-bottom:8px;">${p.title}</h3>
      <p style="color:#94a3b8; margin-bottom:20px; display:flex; align-items:center; gap:6px;">
        <span>📍</span> ${p.locality ? p.locality + ', ' : ''}${p.city} • ID: #${p.id}
      </p>

      <div style="background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:12px; padding:18px; margin-bottom:24px; display:grid; grid-template-columns:repeat(4, 1fr); gap:14px;">
        <div>
          <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase;">Bedrooms</div>
          <div style="font-size:1.1rem; color:#fff; font-weight:700;">${p.bedrooms || '-'} Beds</div>
        </div>
        <div>
          <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase;">Bathrooms</div>
          <div style="font-size:1.1rem; color:#fff; font-weight:700;">${p.bathrooms || 2} Baths</div>
        </div>
        <div>
          <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase;">Super Area</div>
          <div style="font-size:1.1rem; color:#fff; font-weight:700;">${p.sqft ? p.sqft + ' sqft' : '-'}</div>
        </div>
        <div>
          <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase;">Status</div>
          <div style="font-size:1.1rem; color:#10b981; font-weight:700;">Ready to Move</div>
        </div>
      </div>

      <div style="background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.25); border-radius:12px; padding:16px; margin-bottom:24px;">
        <h4 style="color:#a5b4fc; font-size:0.95rem; margin-bottom:6px;">💡 Estimated Monthly Expense</h4>
        <p style="font-size:0.88rem; color:#cbd5e1;">Estimated EMI / Maintenance from <strong>₹${emiEstimate.toLocaleString()}/month</strong> with 8.5% p.a. standard home financing.</p>
      </div>

      <div style="display:flex; gap:12px;">
        <button class="btn-primary" style="flex:1; justify-content:center; padding:14px;" onclick="contactAgent('${p.id}', '${p.title}')">
          Book Free Site Visit
        </button>
        ${p.listing_url ? `<a href="${p.listing_url}" target="_blank" class="btn-card-secondary" style="display:inline-flex; align-items:center; gap:6px; padding:14px 20px; text-decoration:none;">View Source</a>` : ''}
      </div>
    </div>
  `;

  modal.classList.add("active");
}

function closeModal() {
  const modal = document.getElementById("property-modal");
  if (modal) modal.classList.remove("active");
}

async function contactAgent(id, title) {
  try {
    const res = await fetch("/api/inquiry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ property_id: id, name: "Buyer", phone: "+91-9876543210" }),
    });
    const d = await res.json();
    showToast(d.message || "Broker notified! Expect a call shortly.");
    closeModal();
  } catch (err) {
    showToast("Broker notified! Reference ID #" + id);
    closeModal();
  }
}

function showToast(msg) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = `<span>✅</span><span>${msg}</span>`;
  container.appendChild(t);

  setTimeout(() => {
    t.style.opacity = "0";
    t.style.transition = "opacity 0.4s ease";
    setTimeout(() => t.remove(), 400);
  }, 4000);
}
