export default {
  template: `
  <div class="card" style="padding:14px;margin-top:12px;">
    <div class="section-title" style="margin-top:0;">🔬 回测模拟</div>
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
      <input class="search-input" v-model="addr" placeholder="输入钱包地址 0x..." style="flex:1;min-width:250px;max-width:420px;">
      <select v-model="days" class="search-input" style="max-width:100px;">
        <option :value="7">7天</option>
        <option :value="30">30天</option>
        <option :value="90">90天</option>
      </select>
      <button class="btn" @click="run" :disabled="running">{{ running ? '计算中...' : '开始回测' }}</button>
    </div>
    <div v-if="result && !result.error" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;">
      <div class="summary-item"><span class="summary-label">初始资金</span><span class="summary-value mono">\${{ result.initial_capital }}</span></div>
      <div class="summary-item"><span class="summary-label">最终市值</span><span class="summary-value mono green">\${{ result.final_value }}</span></div>
      <div class="summary-item"><span class="summary-label">累计盈亏</span><span class="summary-value mono" :class="(result.pnl||0)>=0?'green':'red'">\${{ (result.pnl||0).toFixed(2) }}</span></div>
      <div class="summary-item"><span class="summary-label">回报率</span><span class="summary-value mono" :class="(result.pnl_pct||0)>=0?'green':'red'">{{ (result.pnl_pct||0)>=0?'+':''}}{{ result.pnl_pct }}%</span></div>
      <div class="summary-item"><span class="summary-label">已实现盈亏</span><span class="summary-value mono" :class="(result.realized_pnl||0)>=0?'green':'red'" :title="'基于卖出交易的实际盈亏'">\${{ (result.realized_pnl||0).toFixed(2) }}</span></div>
      <div class="summary-item"><span class="summary-label">现金余额</span><span class="summary-value mono muted">\${{ (result.cash_remaining||0).toFixed(2) }}</span></div>
      <div class="summary-item"><span class="summary-label">模拟交易</span><span class="summary-value mono muted">{{ result.buy_count||0 }}买 / {{ result.sell_count||0 }}卖</span></div>
      <div class="summary-item"><span class="summary-label">持仓中</span><span class="summary-value mono muted">{{ result.open_positions }} 个 · \${{ (result.unrealized_value||0).toFixed(0) }}</span></div>
      <div class="summary-item" v-if="result.expired_positions"><span class="summary-label">已过期(未计入)</span><span class="summary-value mono amber">{{ result.expired_positions }} 个 · \${{ (result.expired_value||0).toFixed(0) }}</span></div>
    </div>
    <div v-if="result && result.warnings && result.warnings.length" style="margin-top:10px;">
      <div v-for="w in result.warnings" :key="w" style="font-size:11px;color:var(--amber);padding:3px 0;">⚠️ {{ w }}</div>
    </div>
    <div v-if="result && result.error" class="muted" style="padding:10px;">{{ result.error }}</div>
  </div>`,
  data(){ return { addr:'', days:30, running:false, result:null }; },
  methods: {
    async run(){
      if(!this.addr.trim()) return;
      this.running=true; this.result=null;
      try{
        const r=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:this.addr.trim(),days:this.days})});
        this.result=await r.json();
      }catch(e){ this.result={error:'网络错误'}; }
      this.running=false;
    }
  }
};
