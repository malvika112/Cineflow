const ADMIN_TOKEN_KEY = 'cf_admin_token';

const Admin = {
  getToken() {
    return localStorage.getItem(ADMIN_TOKEN_KEY) || 'admin-dev-token';
  },
  setToken(t) {
    localStorage.setItem(ADMIN_TOKEN_KEY, t);
  },
  async req(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': this.getToken(),
        ...(opts.headers || {}),
      },
    });
    if (res.status === 401) {
      const newToken = prompt('Admin token required:', this.getToken());
      if (newToken) {
        this.setToken(newToken);
        return this.req(path, opts);
      }
      throw new Error('Unauthorized');
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
  },
  formatRupees(paise) {
    return `\u20B9${(paise / 100).toFixed(2)}`;
  },
};
