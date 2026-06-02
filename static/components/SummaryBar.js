export default {
  template: `
  <div class="summary-bar">
    <div class="summary-item"><span class="summary-label">总本金</span><span class="summary-value mono">\${{ fmt(s.total_capital) }}</span></div>
    <div class="summary-item"><span class="summary-label">可用现金</span><span class="summary-value mono">\${{ fmt(s.total_cash) }}</span></div>
    <div class="summary-item"><span class="summary-label">总市值</span><span class="summary-value mono green">\${{ fmt(s.total_value) }}</span></div>
    <div class="summary-item"><span class="summary-label">累计盈亏</span><span class="summary-value mono" :class="pnlClass">\${{ fmtPnl(s.total_pnl) }}</span></div>
    <div class="summary-item"><span class="summary-label">盈亏%</span><span class="summary-value mono" :class="pnlClass">{{ fmtPnlPct(s.total_pnl_pct) }}%</span></div>
    <div class="summary-item"><span class="summary-label">胜率</span><span class="summary-value mono muted" style="font-size:14px;">{{ s.win_rate != null ? s.win_rate + '%' : '—' }}</span></div>
    <div class="summary-item"><span class="summary-label">最后扫描</span><span class="summary-value mono muted" style="font-size:12px;">{{ s.last_scan || '—' }}</span></div>
  </div>`,
  props: { s: { type: Object, default: () => ({}) } },
  computed: { pnlClass() { return (this.s.total_pnl || 0) >= 0 ? 'green' : 'red'; } },
  methods: {
    fmt(v) { return (v || 0).toFixed(2); },
    fmtPnl(v) { const n = v || 0; return (n >= 0 ? '+' : '') + n.toFixed(2); },
    fmtPnlPct(v) { const n = v || 0; return (n >= 0 ? '+' : '') + n.toFixed(2); }
  }
};
