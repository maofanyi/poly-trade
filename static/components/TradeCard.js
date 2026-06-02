export default {
  template: `<div class="trade-card">
    <div class="trade-card-header">
      <span class="trade-card-name">{{ walletName }}</span>
      <span style="display:flex;align-items:center;gap:8px;">
        <span class="cat-tag" :class="catClass">{{ walletCat }}</span>
        <button class="btn danger" @click="$emit('remove')" style="font-size:9px;padding:2px 8px;">✕</button>
      </span>
    </div>
    <div class="trade-card-body">
      <div v-for="t in trades" :key="t.id" class="trade-row">
        <span class="trade-side" :class="(t.side||'').toLowerCase()">{{ t.side==='BUY'?'买':'卖' }}</span>
        <span class="trade-qty">{{ (t.size||0).toFixed(0) }}</span>
        <span class="trade-market">{{ (t.slug||'').slice(0,35) }}</span>
        <span class="trade-usd">\${{ (t.sim_usd||0).toFixed(2) }}</span>
        <span class="trade-slip" :class="(t.slippage||0)<0.01?'green':'red'">{{ t.slippage != null ? '\$'+t.slippage.toFixed(4) : '—' }}</span>
        <span class="trade-status" :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span>
      </div>
    </div>
  </div>`,
  props: { walletName:String, walletCat:String, trades:Array },
  emits: ['remove'],
  computed: { catClass(){ const m={Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'}; return m[this.walletCat]||'w'; } },
  methods: {
    statusClass(s){ if(s==='FILLED')return'status-filled'; if(s==='SKIPPED')return'status-skipped'; return'status-failed'; },
    statusLabel(s){ if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; return'失败'; }
  }
};
