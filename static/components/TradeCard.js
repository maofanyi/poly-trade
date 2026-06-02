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
      <div v-for="t in trades" :key="t.id" class="trade-row" :title="rowTitle(t)">
        <span class="trade-side" :class="(t.side||'').toLowerCase()" :title="t.side==='BUY'?'买入':'卖出'">{{ t.side==='BUY'?'买':'卖' }}</span>
        <span class="trade-qty" title="鲸鱼交易量(份)">{{ (t.size||0).toFixed(0) }}</span>
        <span class="trade-market" :title="t.slug||''">{{ (t.slug||'').slice(0,35) }}</span>
        <span class="trade-usd" :title="'模拟跟单金额: \$'+(t.sim_usd||0).toFixed(2)">\${{ (t.sim_usd||0).toFixed(2) }}</span>
        <span class="trade-slip" :class="slipClass(t)" :title="'鲸鱼价\$'+((t.whale_price)||0).toFixed(4)+' → 成交价\$'+((t.fill_price)||0).toFixed(4)+' | 滑点='+slipPct(t)+'%'">{{ slipPct(t) }}%</span>
        <span class="trade-status" :class="statusClass(t.status)" :title="statusTooltip(t)">{{ statusLabel(t.status) }}</span>
      </div>
    </div>
  </div>`,
  props: { walletName:String, walletCat:String, trades:Array },
  emits: ['remove'],
  computed: { catClass(){ const m={Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'}; return m[this.walletCat]||'w'; } },
  methods: {
    statusClass(s){ if(s==='FILLED')return'status-filled'; if(s==='SKIPPED')return'status-skipped'; return'status-failed'; },
    statusLabel(s){ if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; return'失败'; },
    statusTooltip(t){
      const base = this.statusLabel(t.status);
      if (t.status==='FILLED') return base + ' @ \$' + (t.fill_price||0).toFixed(4);
      if (t.status==='FAILED') return base + ': ' + (t.reason||'未知错误');
      return base;
    },
    slipPct(t){ return (t.whale_price > 0 && t.fill_price) ? Math.abs((t.fill_price - t.whale_price) / t.whale_price * 100).toFixed(2) : '0.00'; },
    slipClass(t){ const p = parseFloat(this.slipPct(t)); return p < 1 ? 'green' : (p < 5 ? 'muted' : 'red'); },
    rowTitle(t){
      return '鲸鱼' + (t.side==='BUY'?'买入':'卖出') + ' ' + (t.size||0).toFixed(0) + '份 × \$' + (t.whale_price||0).toFixed(4) + ' | 跟单\$' + (t.sim_usd||0).toFixed(2) + ' | 成交\$' + (t.fill_price||'?').toString() + ' | 滑点' + this.slipPct(t) + '%';
    }
  }
};
