// ROAST — каталог, кошик і оформлення замовлення без фреймворків.
const API_URL = "/api/orders";
const DEMO = location.hostname.endsWith("github.io") || location.protocol === "file:";
const FREE_FROM = 1000;
const DELIVERY = 80;
const CART_KEY = "roast-cart-v1";
const ROAST = { light: "Світле", medium: "Середнє", dark: "Темне" };
const TYPE = { filter: "Під фільтр", espresso: "Під еспресо", universal: "Універсальна" };
const GRIND = { beans: "Зерно", filter: "Помел під фільтр", espresso: "Помел під еспресо" };

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => `${n.toLocaleString("uk-UA")} ₴`;

let products = [];
const filters = { roast: "", type: "", q: "", sort: "popular" };
let cart = loadCart();

// ---------- Пакет кави (SVG, без зображень) ----------
function bagSVG(p) {
  return `<svg viewBox="0 0 120 160" role="img" aria-label="${esc(p.name)}">
    <path d="M20 22 L100 22 L106 150 Q60 158 14 150 Z" fill="${p.color}"/>
    <path d="M20 22 L100 22 L101 34 L19 34 Z" fill="rgba(0,0,0,.18)"/>
    <path d="M14 150 Q60 158 106 150 L104 120 Q60 128 16 120 Z" fill="rgba(0,0,0,.12)"/>
    <rect x="30" y="52" width="60" height="56" rx="6" fill="#fffaf3"/>
    <text x="60" y="70" text-anchor="middle" font-family="Fraunces, serif" font-weight="700" font-size="11" fill="#1f1a17">ROAST</text>
    <text x="60" y="86" text-anchor="middle" font-family="Manrope, sans-serif" font-size="7.5" fill="#7a6e64">${esc(p.origin.split(" ")[0].toUpperCase())}</text>
    <circle cx="48" cy="98" r="3" fill="${p.roast === "light" ? "#d9a35b" : p.roast === "medium" ? "#8a5a3b" : "#3b2a22"}"/>
    <circle cx="60" cy="98" r="3" fill="${p.roast !== "light" ? (p.roast === "medium" ? "#8a5a3b" : "#3b2a22") : "#eadfce"}"/>
    <circle cx="72" cy="98" r="3" fill="${p.roast === "dark" ? "#3b2a22" : "#eadfce"}"/>
    <rect x="52" y="14" width="16" height="10" rx="2" fill="rgba(0,0,0,.25)"/>
  </svg>`;
}

// ---------- Каталог ----------
async function loadProducts() {
  const res = await fetch("data/products.json");
  products = await res.json();
  $("#heroBag").innerHTML = bagSVG(products[0]);
  renderGrid();
  renderCart();
}

function visibleProducts() {
  const q = filters.q.trim().toLowerCase();
  let list = products.filter((p) =>
    (!filters.roast || p.roast === filters.roast) &&
    (!filters.type || p.type === filters.type) &&
    (!q || [p.name, p.origin, ...p.notes].join(" ").toLowerCase().includes(q))
  );
  if (filters.sort === "price-asc") list = [...list].sort((a, b) => a.price - b.price);
  if (filters.sort === "price-desc") list = [...list].sort((a, b) => b.price - a.price);
  if (filters.sort === "popular") list = [...list].sort((a, b) => b.rating - a.rating);
  return list;
}

function renderGrid() {
  const list = visibleProducts();
  $("#empty").hidden = list.length > 0;
  $("#grid").innerHTML = list.map((p, i) => `
    <article class="card" style="animation-delay:${i * 40}ms">
      <div class="card-art" style="background:${p.color}22">
        ${p.badge ? `<span class="badge">${esc(p.badge)}</span>` : ""}
        ${bagSVG(p)}
      </div>
      <h3>${esc(p.name)}</h3>
      <div class="meta"><span>${ROAST[p.roast]} обсмаження</span>·<span>${TYPE[p.type]}</span>·<span>★ ${p.rating}</span></div>
      <div class="notes">${p.notes.map((n) => `<span>${esc(n)}</span>`).join("")}</div>
      <div class="card-foot">
        <select aria-label="Помел" data-grind="${p.id}">
          ${Object.entries(GRIND).map(([k, v]) => `<option value="${k}" ${k === defaultGrind(p) ? "selected" : ""}>${v}</option>`).join("")}
        </select>
        <div class="price">${money(p.price)} <small>/ ${p.weight} г</small></div>
        <button class="add" data-add="${p.id}">У кошик</button>
      </div>
    </article>`).join("");
}

function defaultGrind(p) {
  return p.type === "espresso" ? "espresso" : p.type === "filter" ? "filter" : "beans";
}

// ---------- Кошик ----------
function loadCart() {
  try { return JSON.parse(localStorage.getItem(CART_KEY)) || []; } catch { return []; }
}
function saveCart() {
  try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch {}
}
function addToCart(id, grind) {
  const line = cart.find((l) => l.id === id && l.grind === grind);
  if (line) line.qty = Math.min(line.qty + 1, 20);
  else cart.push({ id, grind, qty: 1 });
  saveCart();
  renderCart();
  const count = $("#cartCount");
  count.classList.remove("bump");
  void count.offsetWidth;
  count.classList.add("bump");
  const p = products.find((x) => x.id === id);
  toast(`«${p.name}» у кошику`);
}

function totals() {
  const subtotal = cart.reduce((s, l) => s + (products.find((p) => p.id === l.id)?.price || 0) * l.qty, 0);
  const delivery = subtotal === 0 ? 0 : subtotal >= FREE_FROM ? 0 : DELIVERY;
  return { subtotal, delivery, total: subtotal + delivery };
}

function renderCart() {
  if (!products.length) return;
  cart = cart.filter((l) => products.some((p) => p.id === l.id));
  $("#cartCount").textContent = cart.reduce((s, l) => s + l.qty, 0);
  $("#cartEmpty").hidden = cart.length > 0;
  $("#cartList").innerHTML = cart.map((l, i) => {
    const p = products.find((x) => x.id === l.id);
    return `<li class="cart-item">
      <div class="thumb" style="background:${p.color}22">${bagSVG(p)}</div>
      <div><b>${esc(p.name)}</b><small>${GRIND[l.grind]} · ${money(p.price)}</small>
        <div class="qty"><button data-dec="${i}" aria-label="Менше">−</button><span>${l.qty}</span><button data-inc="${i}" aria-label="Більше">+</button></div>
      </div>
      <div><div class="line-price">${money(p.price * l.qty)}</div><button class="remove" data-rm="${i}">Видалити</button></div>
    </li>`;
  }).join("");
  const t = totals();
  $("#subtotal").textContent = money(t.subtotal);
  $("#deliveryCost").textContent = t.subtotal === 0 ? "—" : t.delivery ? money(t.delivery) : "Безкоштовно";
  $("#total").textContent = money(t.total);
  const left = FREE_FROM - t.subtotal;
  $("#shipBar").style.width = `${Math.min(100, (t.subtotal / FREE_FROM) * 100)}%`;
  $("#shipText").textContent = t.subtotal === 0 ? "" : left > 0 ? `Ще ${money(left)} до безкоштовної доставки` : "🎉 Доставка безкоштовна";
  if (view === "cart") $("#primaryBtn").disabled = cart.length === 0;
}

// ---------- Шухляда кошика ----------
let view = "cart";
const drawer = $("#drawer");
const overlay = $("#overlay");

function openDrawer() {
  overlay.hidden = false;
  requestAnimationFrame(() => overlay.classList.add("show"));
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  setView(view === "done" ? "cart" : view);
}
function closeDrawer() {
  overlay.classList.remove("show");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  setTimeout(() => (overlay.hidden = true), 300);
}
function setView(v) {
  view = v;
  $("#cartView").hidden = v !== "cart";
  $("#checkoutView").hidden = v !== "checkout";
  $("#doneView").hidden = v !== "done";
  $("#drawerFoot").hidden = v === "done";
  $("#backBtn").hidden = v !== "checkout";
  $("#drawerTitle").textContent = { cart: "Кошик", checkout: "Оформлення", done: "Готово" }[v];
  const btn = $("#primaryBtn");
  btn.textContent = v === "checkout" ? "Підтвердити замовлення" : "Оформити замовлення";
  btn.disabled = v === "cart" && cart.length === 0;
}

// ---------- Оформлення ----------
const PHONE_RE = /^\+?[\d\s\-()]{9,18}$/;
function validate(data) {
  const e = {};
  if (data.name.trim().length < 2) e.name = "Вкажіть ім'я";
  if (!PHONE_RE.test(data.phone.trim())) e.phone = "Вкажіть коректний номер";
  if (data.city.trim().length < 2) e.city = "Вкажіть місто";
  if (!data.branch.trim()) e.branch = "Вкажіть відділення";
  return e;
}
function showErrors(errors) {
  const form = $("#checkoutView");
  form.querySelectorAll(".err").forEach((el) => {
    const f = el.dataset.for;
    el.textContent = errors[f] || "";
    form.elements[f].classList.toggle("invalid", Boolean(errors[f]));
  });
}

async function submitOrder() {
  const form = $("#checkoutView");
  const data = Object.fromEntries(new FormData(form));
  const errors = validate(data);
  showErrors(errors);
  $("#formError").textContent = "";
  if (Object.keys(errors).length) return;

  const btn = $("#primaryBtn");
  btn.disabled = true;
  btn.textContent = "Надсилаємо…";
  const { total } = totals();
  try {
    let orderId;
    if (DEMO) {
      await new Promise((r) => setTimeout(r, 800));
      orderId = "DEMO";
    } else {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer: data, items: cart, website: data.website }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body.ok) {
        if (body.errors) showErrors(body.errors);
        throw new Error(body.error || "Перевірте дані форми");
      }
      orderId = body.id;
    }
    $("#doneText").innerHTML = DEMO
      ? `Демо-режим: у робочій версії замовлення зберігається в базі, а власник одразу отримує його в Telegram.<br>Сума: <b>${money(total)}</b>`
      : `Номер замовлення <b>#${orderId}</b> на суму <b>${money(total)}</b>.<br>Ми зателефонуємо для підтвердження, а статус можна перевірити в нашому Telegram-боті.`;
    cart = [];
    saveCart();
    form.reset();
    renderCart();
    setView("done");
  } catch (err) {
    $("#formError").textContent = err.message || "Не вдалося надіслати. Спробуйте ще раз.";
  } finally {
    if (view === "checkout") {
      btn.disabled = false;
      btn.textContent = "Підтвердити замовлення";
    }
  }
}

// ---------- Toast ----------
let toastTimer;
function toast(text) {
  const el = $("#toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 1800);
}

// ---------- Події ----------
document.addEventListener("click", (e) => {
  const t = e.target.closest("button");
  if (!t) return;
  if (t.dataset.add) {
    const grind = $(`select[data-grind="${t.dataset.add}"]`).value;
    addToCart(t.dataset.add, grind);
  }
  if (t.dataset.inc) { cart[+t.dataset.inc].qty = Math.min(cart[+t.dataset.inc].qty + 1, 20); saveCart(); renderCart(); }
  if (t.dataset.dec) {
    const l = cart[+t.dataset.dec];
    l.qty -= 1;
    if (l.qty <= 0) cart.splice(+t.dataset.dec, 1);
    saveCart(); renderCart();
  }
  if (t.dataset.rm) { cart.splice(+t.dataset.rm, 1); saveCart(); renderCart(); }
  if (t.dataset.roast !== undefined) {
    filters.roast = t.dataset.roast;
    document.querySelectorAll("#roastChips .chip").forEach((c) => c.classList.toggle("active", c === t));
    renderGrid();
  }
  if (t.dataset.type !== undefined) {
    filters.type = t.dataset.type;
    document.querySelectorAll("#typeChips .chip").forEach((c) => c.classList.toggle("active", c === t));
    renderGrid();
  }
});
$("#search").addEventListener("input", (e) => { filters.q = e.target.value; renderGrid(); });
$("#sort").addEventListener("change", (e) => { filters.sort = e.target.value; renderGrid(); });
$("#cartBtn").addEventListener("click", openDrawer);
$("#closeDrawer").addEventListener("click", closeDrawer);
overlay.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && drawer.classList.contains("open")) closeDrawer(); });
$("#primaryBtn").addEventListener("click", () => (view === "cart" ? setView("checkout") : submitOrder()));
$("#backBtn").addEventListener("click", () => setView("cart"));
$("#checkoutView").addEventListener("submit", (e) => { e.preventDefault(); submitOrder(); });

loadProducts();
