import TradeCard from './TradeCard.js';
export default {
  components: { TradeCard },
  template: `<div class="trade-grid">
    <trade-card v-for="name in Object.keys(groupedTrades)" :key="name" :wallet-name="name" :wallet-cat="cats[name]||'—'" :wallet-id="ids[name]" :trades="groupedTrades[name]" @remove="$emit('remove', name)" @detail="(trade,cat)=>$emit('detail',trade,cat)" />
    <div v-if="Object.keys(groupedTrades).length===0" class="empty">暂无成交记录，等待新交易...</div>
  </div>`,
  props: { trades: { type: Array, default: () => [] }, wallets: { type: Array, default: () => [] } },
  emits: ['remove','detail'],
  computed: {
    groupedTrades() { const g={}; for(const t of this.trades){ const n=t.wallet_name||'?'; if(!g[n])g[n]=[]; if(g[n].length<8)g[n].push(t); } return g; },
    cats() { const c={}; for(const w of this.wallets) c[w.name]=w.category; return c; },
    ids() { const m={}; for(const w of this.wallets) m[w.name]=w.id; return m; }
  }
};
