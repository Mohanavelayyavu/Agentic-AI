// ---------------------------------------------------------
// NPK button controls (also drive the hero vial signature)
// ---------------------------------------------------------
const heroFillHeights = { low: "30%", medium: "60%", high: "90%" };

document.querySelectorAll(".npk-control").forEach((control) => {
  const inputName = control.dataset.input;
  const hiddenInput = document.getElementById(inputName);
  const buttons = control.querySelectorAll(".npk-buttons button");
  const heroVialClass = { nitrogen: "n", phosphorus: "p", potassium: "k" }[inputName];
  const heroFill = document.querySelector(`.vial-fill--${heroVialClass}`);

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      hiddenInput.value = btn.dataset.value;
      if (heroFill) heroFill.style.height = heroFillHeights[btn.dataset.value];
    });
  });
});

// ---------------------------------------------------------
// pH slider readout
// ---------------------------------------------------------
const phInput = document.getElementById("ph");
const phValue = document.getElementById("phValue");
phInput.addEventListener("input", () => {
  phValue.textContent = parseFloat(phInput.value).toFixed(1);
});

// ---------------------------------------------------------
// Farming method segmented control
// ---------------------------------------------------------
const farmingTypeInput = document.getElementById("farming_type");
document.querySelectorAll(".segmented-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".segmented-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    farmingTypeInput.value = btn.dataset.value;
  });
});

// ---------------------------------------------------------
// Weather auto-fill
// ---------------------------------------------------------
const weatherStatus = document.getElementById("weatherStatus");

document.getElementById("useLocationBtn").addEventListener("click", () => {
  if (!navigator.geolocation) {
    weatherStatus.textContent = "Geolocation isn't available in this browser.";
    return;
  }
  weatherStatus.textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude, longitude } = pos.coords;
      weatherStatus.textContent = "Fetching current weather…";
      try {
        const res = await fetch(`/api/weather?lat=${latitude}&lng=${longitude}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Weather lookup failed");
        if (data.temperature_c !== null && data.temperature_c !== undefined) {
          document.getElementById("temperature").value = data.temperature_c;
        }
        if (data.humidity_pct !== null && data.humidity_pct !== undefined) {
          document.getElementById("humidity").value = data.humidity_pct;
        }
        if (data.rainfall_mm !== null && data.rainfall_mm !== undefined) {
          document.getElementById("rainfall").value = data.rainfall_mm;
        }
        weatherStatus.textContent = "Weather filled in from your location. Feel free to adjust it.";
      } catch (err) {
        weatherStatus.textContent = "Couldn't fetch weather automatically — please enter it manually.";
      }
    },
    () => {
      weatherStatus.textContent = "Location permission denied — please enter weather manually.";
    }
  );
});

// ---------------------------------------------------------
// Recommendation form submit
// ---------------------------------------------------------
const form = document.getElementById("recommendForm");
const formError = document.getElementById("formError");
const resultsCard = document.getElementById("resultsCard");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.textContent = "";

  const nitrogen = document.getElementById("nitrogen").value;
  const phosphorus = document.getElementById("phosphorus").value;
  const potassium = document.getElementById("potassium").value;

  if (!nitrogen || !phosphorus || !potassium) {
    formError.textContent = "Please set a level for nitrogen, phosphorus, and potassium.";
    return;
  }

  const crop = document.getElementById("crop").value;
  if (!crop) {
    formError.textContent = "Please select a crop.";
    return;
  }

  const payload = {
    crop,
    nitrogen,
    phosphorus,
    potassium,
    ph: phInput.value,
    soil_moisture: document.getElementById("soil_moisture").value || null,
    temperature: document.getElementById("temperature").value || null,
    humidity: document.getElementById("humidity").value || null,
    rainfall: document.getElementById("rainfall").value || null,
    season: document.getElementById("season").value || null,
    farming_type: farmingTypeInput.value,
    land_area: document.getElementById("land_area").value || null,
    area_unit: document.getElementById("area_unit").value,
  };

  const submitBtn = document.getElementById("submitBtn");
  submitBtn.disabled = true;
  submitBtn.textContent = "Analyzing…";

  try {
    const res = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    renderResults(data);
  } catch (err) {
    formError.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Get recommendation";
  }
});

function renderResults(data) {
  // Chips
  const chipList = document.getElementById("fertilizerChips");
  chipList.innerHTML = "";
  (data.fertilizer_list || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    chipList.appendChild(li);
  });

  // Quantities
  const qtyBlock = document.getElementById("quantityBlock");
  const qtyBody = document.querySelector("#quantityTable tbody");
  qtyBody.innerHTML = "";
  if (data.quantities && data.quantities.length) {
    data.quantities.forEach((q) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${q.name}</td><td>${q.kg_per_acre}</td><td>${q.estimated_kg} kg</td>`;
      qtyBody.appendChild(tr);
    });
    qtyBlock.hidden = false;
  } else {
    qtyBlock.hidden = true;
  }

  // Tips
  const tipsBlock = document.getElementById("tipsBlock");
  const tipsList = document.getElementById("tipsList");
  tipsList.innerHTML = "";
  if (data.tips && data.tips.length) {
    data.tips.forEach((t) => {
      const li = document.createElement("li");
      li.textContent = t;
      tipsList.appendChild(li);
    });
    tipsBlock.hidden = false;
  } else {
    tipsBlock.hidden = true;
  }

  // Advice
  document.getElementById("adviceText").textContent = data.advice || "";

  // Notes
  const notesBlock = document.getElementById("notesBlock");
  const notesList = document.getElementById("notesList");
  notesList.innerHTML = "";
  if (data.context && data.context.length) {
    data.context.forEach((n) => {
      const li = document.createElement("li");
      li.textContent = n;
      notesList.appendChild(li);
    });
    notesBlock.hidden = false;
  } else {
    notesBlock.hidden = true;
  }

  resultsCard.hidden = false;
  resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------
// Nearby shops + Leaflet map (OpenStreetMap tiles, no API key)
// ---------------------------------------------------------
let map = null;
let shopMarkers = [];
let userMarker = null;

function initMap(lat, lng) {
  if (map) {
    map.remove();
    shopMarkers = [];
  }
  map = L.map("map").setView([lat, lng], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  const youIcon = L.divIcon({
    className: "you-are-here-marker",
    html: '<span></span>',
    iconSize: [16, 16],
  });
  userMarker = L.marker([lat, lng], { icon: youIcon }).addTo(map).bindPopup("You are here");
}

const shopsStatus = document.getElementById("shopsStatus");
const shopsLayout = document.getElementById("shopsLayout");
const shopList = document.getElementById("shopList");

document.getElementById("findShopsBtn").addEventListener("click", () => {
  if (!navigator.geolocation) {
    shopsStatus.textContent = "Geolocation isn't available in this browser.";
    return;
  }
  shopsStatus.textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude, longitude } = pos.coords;
      try {
        shopsLayout.hidden = false;
        initMap(latitude, longitude);

        shopsStatus.textContent = "Searching OpenStreetMap for nearby shops…";
        const res = await fetch(`/api/nearby-shops?lat=${latitude}&lng=${longitude}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Shop search failed.");

        renderShops(data.shops || []);
      } catch (err) {
        shopsStatus.textContent = err.message;
      }
    },
    () => {
      shopsStatus.textContent = "Location permission denied — enable location access to find nearby shops.";
    }
  );
});

function renderShops(shops) {
  shopList.innerHTML = "";
  shopMarkers.forEach((m) => m.remove());
  shopMarkers = [];

  if (!shops.length) {
    shopsStatus.textContent =
      "No fertilizer/agro shops are tagged on OpenStreetMap near you yet. Try a wider area, " +
      "or add missing shops yourself at openstreetmap.org — it's a community map.";
    return;
  }
  shopsStatus.textContent = `Found ${shops.length} nearby shop${shops.length === 1 ? "" : "s"} (via OpenStreetMap).`;

  const bounds = [[userMarker.getLatLng().lat, userMarker.getLatLng().lng]];

  shops.forEach((shop) => {
    if (shop.lat && shop.lng) {
      const marker = L.marker([shop.lat, shop.lng])
        .addTo(map)
        .bindPopup(`<strong>${shop.name}</strong><br>${shop.address || ""}`);
      shopMarkers.push(marker);
      bounds.push([shop.lat, shop.lng]);
    }

    const li = document.createElement("li");
    const contactBits = [];
    if (shop.phone) contactBits.push(shop.phone);
    if (shop.website) contactBits.push(`<a href="${shop.website}" target="_blank" rel="noopener">website</a>`);
    const contactText = contactBits.length ? contactBits.join(" · ") : "";
    li.innerHTML = `
      <p class="shop-name">${shop.name || "Unnamed shop"}</p>
      <p class="shop-meta">${shop.address || "Address not mapped yet"}</p>
      ${contactText ? `<p class="shop-meta">${contactText}</p>` : ""}
    `;
    shopList.appendChild(li);
  });

  if (bounds.length > 1) {
    map.fitBounds(bounds, { padding: [30, 30] });
  }
}
