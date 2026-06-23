/**
 * Shared client-side state. No framework, no build step — the assignment
 * explicitly only grades backend architecture, so the frontend stays as
 * simple as it can while still being honest about real flows (polling,
 * cart persistence across pages via localStorage).
 */
const API_BASE = ''; // same origin, served from /app

const CinemaFlo = {
  getSession() {
    const raw = localStorage.getItem('cf_session');
    return raw ? JSON.parse(raw) : null;
  },
  setSession(session) {
    localStorage.setItem('cf_session', JSON.stringify(session));
  },
  getCart() {
    const raw = localStorage.getItem('cf_cart');
    return raw ? JSON.parse(raw) : {};
  },
  setCart(cart) {
    localStorage.setItem('cf_cart', JSON.stringify(cart));
  },
  clearCart() {
    localStorage.removeItem('cf_cart');
  },
  cartCount(cart) {
    return Object.values(cart).reduce((sum, q) => sum + q, 0);
  },

  async createSession(seatNumber, screenId) {
    const res = await fetch(`${API_BASE}/api/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seat_number: seatNumber, screen_id: screenId }),
    });
    if (!res.ok) throw new Error('Could not start session');
    return res.json();
  },

  async getMenu() {
    const res = await fetch(`${API_BASE}/api/menu`);
    if (!res.ok) throw new Error('Could not load menu');
    return res.json();
  },

  async validateCart(items, offerCode) {
    const session = this.getSession();
    const res = await fetch(`${API_BASE}/api/cart/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_token: session.token,
        items,
        offer_code: offerCode || null,
      }),
    });
    if (!res.ok) throw new Error('Could not validate cart');
    return res.json();
  },

  async checkout(items, offerCode) {
    const session = this.getSession();
    const res = await fetch(`${API_BASE}/api/checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_token: session.token,
        seat_number: session.seat_number,
        items,
        offer_code: offerCode || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      const err = new Error(data.detail || 'Checkout failed');
      err.status = res.status;
      throw err;
    }
    return data;
  },

  async getOrder(orderId) {
    const res = await fetch(`${API_BASE}/api/orders/${orderId}`);
    if (!res.ok) throw new Error('Order not found');
    return res.json();
  },

  formatRupees(paise) {
    return `\u20B9${(paise / 100).toFixed(2)}`;
  },

  toast(message, isError = false) {
    let el = document.getElementById('cf-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'cf-toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.className = 'toast show' + (isError ? ' error' : '');
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.remove('show'), 2500);
  },
};
