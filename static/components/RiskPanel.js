export default {
  template: `
  <div class="card" style="padding:12px 16px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <span class="section-title" style="margin:0;padding:0;border:none;">&#x1F6E1;&#xFE0F; 风控状态</span>
      <button class="btn muted" style="font-size:10px;padding:3px 8px;" @click="load()">刷新</button>
    </div>
    <div v-if="loading" class="empty">加载中...</div>
    <div v-else>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;">
        <div>
          <span class="muted">今日亏损:</span>
          <span :class="todayLossPct > 80 ? 'red' : todayLossPct > 40 ? 'amber' : ''" style="font-weight:600;">
            \${{ risk.today_loss }} / \${{ risk.daily_loss_limit }}
            ({{ todayLossPct }}%)
          </span>
        </div>
        <div>
          <span class="muted">持仓数量:</span>
          <span :class="risk.open_positions >= risk.max_positions ? 'red' : ''" style="font-weight:600;">
            {{ risk.open_positions }} / {{ risk.max_positions }}
          </span>
        </div>
        <div>
          <span class="muted">单仓上限:</span>
          <span class="mono">\${{ risk.max_per_market }}</span>
        </div>
        <div>
          <span class="muted">全局熔断:</span>
          <span :class="risk.circuit_breaker ? 'red' : 'green'" style="font-weight:600;">
            {{ risk.circuit_breaker ? '🔴 已触发' : '🟢 正常' }}
          </span>
        </div>
      </div>
    </div>
  </div>`,
  data() {
    return { risk: { today_loss: 0, daily_loss_limit: 25, open_positions: 0, max_positions: 10, max_per_market: 25, circuit_breaker: false }, loading: true };
  },
  mounted() { this.load(); },
  computed: {
    todayLossPct() {
      const v = this.risk.today_loss / (this.risk.daily_loss_limit || 1) * 100;
      return Math.round(v);
    }
  },
  methods: {
    async load() {
      this.loading = true;
      try {
        const r = await fetch('/api/state');
        if (r.ok) {
          const d = await r.json();
          this.risk = d.risk || this.risk;
        }
      } catch(e) { console.error(e); }
      finally { this.loading = false; }
    }
  }
};
