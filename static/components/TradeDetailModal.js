export default {
  template: `
  <div v-if="trade" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <span class="modal-title">📋 交易详情</span>
        <button class="modal-close" @click="$emit('close')">✕</button>
      </div>

      <!-- Price Chart -->
      <div class="modal-section">
        <div class="modal-section-title">📈 价格走势</div>
        <div class="modal-card" style="padding:0;overflow:hidden;">
          <div ref="chart" style="height:200px;width:100%;"></div>
        </div>
      </div>

      <!-- Market Info -->
      <div class="modal-section">
        <div class="modal-section-title">📋 市场信息</div>
        <div class="modal-card">
          <div class="modal-meta">
            <span class="cat-tag" :class="catClass">{{ catName }}</span>
            <span v-if="isExpired" class="resolved-badge" style="font-size:10px;">已结算</span>
            <span v-else class="resolved-badge" style="font-size:10px;background:rgba(0,230,118,0.12);color:var(--green);">交易中</span>
          </div>
          <div class="modal-market-title">{{ trade.slug || '—' }}</div>
          <div v-if="isExpired" class="modal-resolution">结果: <strong>{{ trade.outcome || '—' }}</strong></div>
        </div>
      </div>

      <!-- Whale Trade -->
      <div class="modal-section">
        <div class="modal-section-title">🐋 鲸鱼交易</div>
        <div class="modal-card">
          <div class="modal-grid">
            <div><span class="label">方向</span><span class="value" :class="(trade.side||'').toLowerCase()">{{ trade.side==='BUY'?'买入':'卖出' }}</span></div>
            <div><span class="label">数量</span><span class="value mono">{{ (trade.size||0).toFixed(0) }} 份</span></div>
            <div><span class="label">价格</span><span class="value mono">\${{ (trade.whale_price||0).toFixed(4) }}</span></div>
            <div><span class="label">交易额</span><span class="value mono">\${{ ((trade.size||0)*(trade.whale_price||0)).toFixed(2) }}</span></div>
          </div>
          <div class="modal-row"><span class="label">时间</span><span class="value mono">{{ trade.timestamp || '—' }}</span></div>
          <div class="modal-row"><span class="label">交易Hash</span><span class="value addr">{{ (trade.txn_hash||'').slice(0,30) }}...</span></div>
        </div>
      </div>

      <!-- Our Copy Trade -->
      <div class="modal-section">
        <div class="modal-section-title">📊 模拟跟单</div>
        <div class="modal-card">
          <div class="modal-grid">
            <div><span class="label">跟单金额</span><span class="value mono green">\${{ (trade.sim_usd||0).toFixed(2) }}</span></div>
            <div><span class="label">成交价</span><span class="value mono">\${{ (trade.fill_price||0).toFixed(4) }}</span></div>
            <div><span class="label">滑点</span><span class="value mono" :class="slipClass">{{ slipPct }}%</span></div>
            <div><span class="label">状态</span><span class="value" :class="statusClass">{{ statusLabel }}</span></div>
          </div>
          <div v-if="trade.pnl_realized" class="modal-row">
            <span class="label">盈亏</span>
            <span class="value mono" :class="trade.pnl_realized>=0?'green':'red'">{{ trade.pnl_realized>=0?'+':'' }}\${{ trade.pnl_realized.toFixed(4) }}</span>
          </div>
        </div>
      </div>

      <!-- External Links -->
      <div class="modal-section">
        <div class="modal-section-title">🔗 外部链接</div>
        <div class="modal-card" style="display:flex;gap:12px;">
          <a :href="'https://polymarket.com/event/'+(trade.slug||'')" target="_blank" class="btn" style="font-size:11px;text-decoration:none;">Polymarket 市场 →</a>
          <a v-if="trade.txn_hash" :href="'https://polygonscan.com/tx/'+trade.txn_hash" target="_blank" class="btn" style="font-size:11px;text-decoration:none;">Polygonscan →</a>
        </div>
      </div>
    </div>
  </div>`,
  props: { trade: Object, walletCat: String },
  emits: ['close'],
  data(){ return { chart: null }; },
  computed: {
    catClass(){ const m={Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'}; return m[this.walletCat]||'w'; },
    catName(){ const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[this.walletCat]||this.walletCat; },
    isExpired(){
      if(!this.trade||!this.trade.slug) return false;
      const m=this.trade.slug.match(/[_-](\d{10})$/);
      if(!m) return false;
      const ts=parseInt(m[1]);
      return ts>1577836800 && ts<2000000000 && (Date.now()/1000-ts)>3600;
    },
    slipPct(){ const t=this.trade; return (t&&t.whale_price>0&&t.fill_price)?Math.abs((t.fill_price-t.whale_price)/t.whale_price*100).toFixed(2):'0.00'; },
    slipClass(){ const p=parseFloat(this.slipPct); return p<1?'green':(p<5?'muted':'red'); },
    statusClass(){
      const s=this.trade?this.trade.status:''; if(s==='FILLED')return'status-filled'; if(s==='SKIPPED')return'status-skipped'; return'status-failed';
    },
    statusLabel(){
      const s=this.trade?this.trade.status:''; if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; return'失败';
    }
  },
  watch: {
    trade: {
      immediate: true,
      async handler(t){
        this.chart = null;
        if(!t||!t.slug) return;
        try {
          const r = await fetch('/api/market/'+encodeURIComponent(t.slug)+'/trades');
          const data = await r.json();
          this.$nextTick(()=> this.renderChart(data.points||[]));
        } catch(e){ console.error('chart:',e); }
      }
    }
  },
  methods: {
    async renderChart(points){
      if(!this.$refs.chart || points.length===0) return;
      // Group trades by outcome
      const yesPts = [], noPts = [];
      const seen = new Set();
      for(const p of points){
        const key = p.t+'_'+p.p;
        if(seen.has(key)) continue;
        seen.add(key);
        const dt = new Date(p.t*1000);
        const label = dt.getMonth()+1+'/'+dt.getDate()+' '+dt.getHours()+':'+String(dt.getMinutes()).padStart(2,'0');
        if(p.o==='Yes'||p.o==='Up'){
          yesPts.push([label, p.p, p.t]);
        } else {
          noPts.push([label, 1-p.p, p.t]);
        }
      }
      yesPts.sort((a,b)=>a[2]-b[2]);
      noPts.sort((a,b)=>a[2]-b[2]);

      import('echarts').then(echarts=>{
        const c = echarts.init(this.$refs.chart, 'dark');
        c.setOption({
          backgroundColor: 'transparent',
          tooltip: { trigger: 'axis', formatter: function(params){ let s=''; for(const p of params){ s+=p.marker+' '+p.seriesName+': '+(p.value*100).toFixed(1)+'%<br/>'; } return s; } },
          grid: { left: 45, right: 15, top: 8, bottom: 30 },
          xAxis: { type: 'category', data: yesPts.map(d=>d[0]), axisLabel: { color: '#5a6b7d', fontSize: 9, rotate: 30, interval: Math.max(1, Math.floor(yesPts.length/8)) }, axisTick: { show: false } },
          yAxis: { type: 'value', min: 0, max: 1, axisLabel: { color: '#5a6b7d', fontSize: 10, formatter: v => (v*100).toFixed(0)+'%' }, splitLine: { lineStyle: { color: '#1c2838' } } },
          series: [
            { name: 'Yes', type: 'line', data: yesPts.map(d=>d[1]), lineStyle: { color: '#00e676', width: 1.5 }, itemStyle: { color: '#00e676' }, symbol: 'none', smooth: true },
            { name: 'No', type: 'line', data: noPts.map(d=>d[1]), lineStyle: { color: '#ff3d4f', width: 1.5 }, itemStyle: { color: '#ff3d4f' }, symbol: 'none', smooth: true }
          ]
        }, true);
      });
    }
  }
};
