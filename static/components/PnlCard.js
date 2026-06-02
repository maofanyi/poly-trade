export default {
  template: `<div class="pnl-card" :class="cardClass">
    <span class="pnl-rank" :class="rankClass">#{{ rank }}</span>
    <div class="pnl-info"><div class="pnl-name">{{ wallet.name }}</div><div class="pnl-cat">{{ catName }} | 现金\${{ (wallet.cash||0).toFixed(0) }}</div></div>
    <div class="pnl-nums"><div class="pnl-value">\${{ (wallet.total_value||0).toFixed(2) }}</div><div class="pnl-pct" :class="pnlColor">{{ pnlSign }}{{ (wallet.pnl_pct||0).toFixed(2) }}%</div></div>
  </div>`,
  props: { wallet: { type: Object, required: true }, rank: { type: Number, default: 0 } },
  computed: {
    cardClass() { return (this.wallet.pnl_pct||0) > 0.5 ? 'win' : ((this.wallet.pnl_pct||0) < -0.5 ? 'loss' : ''); },
    rankClass() { return this.rank === 1 ? 'top1' : (this.rank === 2 ? 'top2' : (this.rank === 3 ? 'top3' : '')); },
    pnlColor() { return (this.wallet.pnl_pct||0) >= 0 ? 'green' : 'red'; },
    pnlSign() { return (this.wallet.pnl_pct||0) >= 0 ? '+' : ''; },
    catName() { const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[this.wallet.category]||this.wallet.category||'—'; }
  }
};
