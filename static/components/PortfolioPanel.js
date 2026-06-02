export default {
  template: `
  <div class="card" style="padding:14px;margin-bottom:12px;">
    <div class="section-title" style="margin-top:0;">📊 组合分析</div>
    <div v-if="data" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <div>
        <div class="muted" style="font-size:11px;margin-bottom:6px;">类别分布</div>
        <div v-for="c in data.category_breakdown" :key="c.category"
          style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid var(--border);">
          <span>{{ catName(c.category) }} ({{ c.wallet_count }}钱包)</span>
          <span class="mono" :class="c.total_pnl>=0?'green':'red'">\${{ c.total_value?.toFixed(0) }} <span style="font-size:10px;">{{ c.total_pnl>=0?'+':'' }}\${{ c.total_pnl?.toFixed(0) }}</span></span>
        </div>
      </div>
      <div>
        <div class="muted" style="font-size:11px;margin-bottom:6px;">最佳表现</div>
        <div v-for="t in data.top_performers" :key="t.name"
          style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid var(--border);">
          <span>{{ t.name }}</span>
          <span class="mono green">+{{ t.pnl_pct?.toFixed(1) }}%</span>
        </div>
      </div>
    </div>
    <div v-if="data && data.market_overlap.length > 0" style="margin-top:12px;">
      <div class="muted" style="font-size:11px;margin-bottom:6px;">⚠️ 市场重叠 (多钱包持有同一市场)</div>
      <div v-for="m in data.market_overlap.slice(0,8)" :key="m.slug"
        style="font-size:11px;padding:2px 0;color:var(--amber);">
        {{ m.wallets }} — {{ m.wallet_count }}个钱包 | {{ (m.slug||'').slice(0,50) }}
      </div>
    </div>
    <div v-if="data" class="muted" style="font-size:10px;margin-top:8px;">总市值 \${{ data.total_value?.toFixed(0) }} · 总盈亏 \${{ data.total_pnl?.toFixed(0) }}</div>
  </div>`,
  props: { data: Object },
  methods: {
    catName(c){ const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[c]||c; }
  }
};
