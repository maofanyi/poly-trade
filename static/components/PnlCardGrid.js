import PnlCard from './PnlCard.js';
export default {
  components: { PnlCard },
  template: `<div class="pnl-grid">
    <pnl-card v-for="(w, idx) in wallets" :key="w.id" :wallet="w" :rank="idx+1" />
    <div v-if="wallets.length===0" class="empty" style="grid-column:1/-1;">暂无盈亏数据，等待首次扫描...</div>
  </div>`,
  props: { wallets: { type: Array, default: () => [] } }
};
