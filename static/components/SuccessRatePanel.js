export default {
  template: `
  <div class="card" style="padding:12px 16px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <span class="section-title" style="margin:0;padding:0;border:none;">📊 跟单成功率</span>
      <button class="btn muted" style="font-size:10px;padding:3px 8px;" @click="load()">刷新</button>
    </div>
    <div v-if="loading" class="empty">加载中...</div>
    <div v-else-if="!data.length" class="empty">暂无交易数据</div>
    <div v-else class="table-wrap" style="max-height:400px;">
      <table>
        <thead>
          <tr>
            <th>钱包</th>
            <th>总交易</th>
            <th>成交</th>
            <th>跳过</th>
            <th>失败</th>
            <th>成功率</th>
            <th>胜率</th>
            <th>跳过原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in data" :key="r.wallet_id">
            <td style="font-weight:600;font-size:12px;">{{ r.name }}</td>
            <td class="mono" style="font-size:12px;">{{ r.total }}</td>
            <td class="mono green" style="font-size:12px;">{{ r.filled }}</td>
            <td class="mono amber" style="font-size:12px;">{{ r.skipped }}</td>
            <td class="mono" :class="r.failed>0?'red':'muted'" style="font-size:12px;">{{ r.failed }}</td>
            <td class="mono" style="font-size:13px;font-weight:700;" :class="rateClass(r.success_rate)">
              {{ r.success_rate != null ? r.success_rate+'%' : '—' }}
            </td>
            <td class="mono muted" style="font-size:12px;">{{ r.win_rate != null ? r.win_rate+'%' : '—' }}</td>
            <td style="font-size:10px;">
              <span v-for="(cnt,reason) in r.skip_reasons" :key="reason"
                :title="reasonLabel(reason)"
                style="display:inline-block;margin:1px 2px;padding:1px 5px;border-radius:3px;background:rgba(255,171,0,0.08);color:var(--amber);white-space:nowrap;">
                {{ reasonLabel(reason) }}:{{ cnt }}
              </span>
              <span v-if="!Object.keys(r.skip_reasons||{}).length" class="muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>`,
  data() {
    return { data: [], loading: false };
  },
  mounted() { this.load(); },
  methods: {
    async load() {
      this.loading = true;
      try {
        const r = await fetch('/api/summary/success-rate');
        if (r.ok) this.data = await r.json();
      } catch (e) { console.error(e); }
      finally { this.loading = false; }
    },
    rateClass(v) {
      if (v == null) return 'muted';
      return v >= 70 ? 'green' : v >= 40 ? 'amber' : 'red';
    },
    reasonLabel(r) {
      const m = {
        price_gap: '价差过大',
        market_closed: '市场关闭',
        size_too_small: '低于最低金额',
        max_positions: '仓位已满',
        daily_limit: '日亏损限额',
        per_market_cap: '单仓上限',
        market_not_found: '市场未找到',
        error: '错误',
      };
      return m[r] || r;
    }
  }
};
