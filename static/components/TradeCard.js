export default {
  template: `<div class="trade-card">
    <div class="trade-card-header">
      <span class="trade-card-name">{{ walletName }}</span>
      <span style="display:flex;align-items:center;gap:8px;">
        <span v-if="totalPosValue" class="muted" style="font-size:10px;" :title="totalPnLTitle">持仓 \${{ totalPosValue }} <span :class="totalUPL>=0?'green':'red'">{{ totalUPL>=0?'+':'' }}\${{ totalUPL.toFixed(2) }}</span></span>
        <span class="cat-tag" :class="catClass">{{ walletCat }}</span>
        <button class="btn danger" @click="$emit('remove')" style="font-size:9px;padding:2px 8px;">✕</button>
      </span>
    </div>
    <div class="trade-card-body">
      <div v-for="p in positions" :key="'p'+p.slug+p.outcome">
        <div class="position-row" @click="$emit('detail', posToTrade(p), walletCat)" style="cursor:pointer;" :title="p.slug">
          <span class="pos-side hold">持仓</span>
          <span class="pos-qty">{{ p.shares.toFixed(0) }}</span>
          <span class="pos-market">{{ (p.slug||'').slice(0,30) }}</span>
          <span class="pos-pnl" :class="(p.unrealized_pnl||0)>=0?'green':'red'">{{ (p.unrealized_pnl||0)>=0?'+':'' }}\${{ (p.unrealized_pnl||0).toFixed(2) }}</span>
          <span class="pos-price muted">@\${{ (p.live_price||p.cost_basis||0).toFixed(4) }}</span>
          <span class="pos-value muted">\${{ (p.value||0).toFixed(2) }}</span>
        </div>
      </div>
      <div v-for="t in trades" :key="t.id">
        <div class="trade-row" :class="{expired: isExpired(t)}" :title="rowTitle(t)" @click="$emit('detail', t, walletCat)" style="cursor:pointer;">
          <span class="trade-side" :class="(t.side||'').toLowerCase()">{{ t.side==='BUY'?'买':'卖' }}</span>
          <span class="trade-qty" title="鲸鱼交易量(份)">{{ (t.size||0).toFixed(0) }}</span>
          <span class="trade-market" :title="t.slug||''">{{ (t.slug||'').slice(0,30) }}</span>
          <span class="trade-usd" :title="'模拟跟单金额: \$'+(t.sim_usd||0).toFixed(2)">\${{ (t.sim_usd||0).toFixed(2) }}</span>
          <span class="trade-slip" :class="slipClass(t)" :title="'鲸鱼价\$'+((t.whale_price)||0).toFixed(4)+' → 成交价\$'+((t.fill_price)||0).toFixed(4)+' | 滑点='+slipPct(t)+'%'">{{ slipPct(t) }}%</span>
          <span class="trade-status" :class="statusClass(t.status)">{{ statusLabel(t.status) }}<span v-if="isExpired(t)" class="resolved-badge">已结算</span></span>
        </div>
      </div>
    </div>
  </div>`,
  props: { walletName:String, walletCat:String, trades:Array, walletId:Number },
  emits: ['remove','detail'],
  data(){ return { positions: [] }; },
  async mounted(){ await this.loadPositions(); },
  computed: {
    catClass(){ const m={Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'}; return m[this.walletCat]||'w'; },
    totalPosValue(){ return this.positions.reduce((s,p)=>s+(p.value||0),0).toFixed(0); },
    totalUPL(){ return this.positions.reduce((s,p)=>s+(p.unrealized_pnl||0),0); },
    totalPnLTitle(){ return this.positions.length+'个持仓 · 浮动盈亏'+(this.totalUPL>=0?'+':'')+'\$'+this.totalUPL.toFixed(2); }
  },
  methods: {
    async loadPositions(){
      if(!this.walletId) return;
      try { const r=await fetch('/api/wallets/'+this.walletId+'/positions'); if(r.ok) this.positions=await r.json(); } catch(e){}
    },
    posToTrade(p){
      return { side:'HOLD', size:p.shares, slug:p.slug, outcome:p.outcome, whale_price:p.cost_basis,
               fill_price:p.live_price, sim_usd:p.value, slippage:0, pnl_realized:p.unrealized_pnl,
               status:'POSITION', txn_hash:'', timestamp:'' };
    },
    statusClass(s){ if(s==='FILLED')return'status-filled'; if(s==='SKIPPED')return'status-skipped'; if(s==='POSITION')return'status-filled'; return'status-failed'; },
    statusLabel(s){ if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; if(s==='POSITION')return'持仓中'; return'失败'; },
    slipPct(t){ return (t.whale_price>0&&t.fill_price)?Math.abs((t.fill_price-t.whale_price)/t.whale_price*100).toFixed(2):'0.00'; },
    slipClass(t){ const p=parseFloat(this.slipPct(t)); return p<1?'green':(p<5?'muted':'red'); },
    isExpired(t){
      if(!t.slug) return false;
      const m=t.slug.match(/[_-](\d{10})$/); if(!m) return false;
      const ts=parseInt(m[1]); return ts>1577836800&&ts<2000000000&&(Date.now()/1000-ts)>3600;
    },
    rowTitle(t){ return '鲸鱼'+(t.side==='BUY'?'买入':'卖出')+' '+(t.size||0).toFixed(0)+'份 × \$'+(t.whale_price||0).toFixed(4)+' | 跟单\$'+(t.sim_usd||0).toFixed(2)+' | 成交\$'+(t.fill_price||'?')+' | 滑点'+this.slipPct(t)+'%'+(this.isExpired(t)?' | 已结算':''); }
  }
};
