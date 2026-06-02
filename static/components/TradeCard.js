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
      <div v-for="t in trades" :key="t.id">
        <div class="trade-row" :class="{expired: isExpired(t)}" :title="rowTitle(t)" @click="toggle(t.id)" style="cursor:pointer;">
          <span class="trade-side" :class="(t.side||'').toLowerCase()">{{ t.side==='BUY'?'买':'卖' }}</span>
          <span class="trade-qty" title="鲸鱼交易量(份)">{{ (t.size||0).toFixed(0) }}</span>
          <span class="trade-market" :title="t.slug||''">{{ (t.slug||'').slice(0,32) }}</span>
          <span class="trade-usd" :title="'模拟跟单金额: \$'+(t.sim_usd||0).toFixed(2)">\${{ (t.sim_usd||0).toFixed(2) }}</span>
          <span class="trade-slip" :class="slipClass(t)" :title="'鲸鱼价\$'+((t.whale_price)||0).toFixed(4)+' → 成交价\$'+((t.fill_price)||0).toFixed(4)+' | 滑点='+slipPct(t)+'%'">{{ slipPct(t) }}%</span>
          <span class="trade-status" :class="statusClass(t.status)">{{ statusLabel(t.status) }}<span v-if="isExpired(t)" class="resolved-badge">已结算</span></span>
        </div>
        <div v-if="expanded === t.id" class="trade-detail">
          <div class="detail-row"><span>市场</span><span>{{ t.slug || '—' }}</span></div>
          <div class="detail-row"><span>结果</span><span>{{ t.outcome || '—' }}</span></div>
          <div class="detail-row"><span>鲸鱼价</span><span>\${{ (t.whale_price||0).toFixed(4) }}</span></div>
          <div class="detail-row"><span>成交价</span><span>\${{ (t.fill_price||0).toFixed(4) }}</span></div>
          <div class="detail-row"><span>跟单金额</span><span>\${{ (t.sim_usd||0).toFixed(2) }}</span></div>
          <div class="detail-row"><span>鲸鱼量</span><span>{{ (t.size||0).toFixed(0) }} 份</span></div>
          <div class="detail-row"><span>滑点</span><span>{{ slipPct(t) }}%</span></div>
          <div v-if="t.pnl_realized" class="detail-row"><span>已实现盈亏</span><span :class="t.pnl_realized>=0?'green':'red'">\${{ t.pnl_realized.toFixed(4) }}</span></div>
          <div class="detail-row"><span>时间</span><span>{{ t.timestamp || '—' }}</span></div>
          <div class="detail-row"><span>状态</span><span :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span></div>
          <div v-if="isExpired(t)" class="detail-row" style="color:var(--amber);"><span>市场状态</span><span>已到期结算</span></div>
          <div class="detail-row"><span>交易Hash</span><span class="addr">{{ (t.txn_hash||'').slice(0,20) }}...</span></div>
        </div>
      </div>
    </div>
  </div>`,
  props: { walletName:String, walletCat:String, trades:Array },
  emits: ['remove'],
  data(){ return { expanded: null }; },
  computed: { catClass(){ const m={Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'}; return m[this.walletCat]||'w'; } },
  methods: {
    toggle(id){ this.expanded = this.expanded === id ? null : id; },
    statusClass(s){ if(s==='FILLED')return'status-filled'; if(s==='SKIPPED')return'status-skipped'; return'status-failed'; },
    statusLabel(s){ if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; return'失败'; },
    slipPct(t){ return (t.whale_price>0&&t.fill_price)?Math.abs((t.fill_price-t.whale_price)/t.whale_price*100).toFixed(2):'0.00'; },
    slipClass(t){ const p=parseFloat(this.slipPct(t)); return p<1?'green':(p<5?'muted':'red'); },
    isExpired(t){
      if(!t.slug) return false;
      const m = t.slug.match(/[_-](\d{10})$/);
      if(!m) return false;
      const ts = parseInt(m[1]);
      return ts > 1577836800 && ts < 2000000000 && (Date.now()/1000 - ts) > 3600;
    },
    rowTitle(t){ return '鲸鱼'+(t.side==='BUY'?'买入':'卖出')+' '+(t.size||0).toFixed(0)+'份 × \$'+(t.whale_price||0).toFixed(4)+' | 跟单\$'+(t.sim_usd||0).toFixed(2)+' | 成交\$'+(t.fill_price||'?')+' | 滑点'+this.slipPct(t)+'%'+(this.isExpired(t)?' | 已结算':''); }
  }
};
