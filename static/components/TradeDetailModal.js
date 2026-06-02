export default {
  template: `
  <div v-if="trade" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <span class="modal-title">📋 交易详情</span>
        <button class="modal-close" @click="$emit('close')">✕</button>
      </div>

      <!-- Price Chart (Spell-style Canvas) -->
      <div class="modal-section">
        <div class="modal-section-title">📈 价格走势</div>
        <div class="modal-card" style="padding:0;overflow:hidden;position:relative;background:#0d1117;">
          <canvas ref="chart" style="width:100%;height:220px;display:block;"></canvas>
          <div v-if="tooltip.visible" class="chart-tooltip" :style="{left:tooltip.x+'px',top:tooltip.y+'px'}">
            <div class="tooltip-label">{{ tooltip.label }}</div>
            <div class="tooltip-value">{{ tooltip.value }}</div>
          </div>
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

      <!-- Position (if HOLD) or Whale Trade -->
      <div class="modal-section" v-if="isPosition()">
        <div class="modal-section-title">💎 持仓详情</div>
        <div class="modal-card">
          <div class="modal-grid">
            <div><span class="label">方向</span><span class="value" style="color:var(--blue);">持仓</span></div>
            <div><span class="label">份额</span><span class="value mono">{{ (trade.size||0).toFixed(0) }} 份</span></div>
            <div><span class="label">成本价</span><span class="value mono">\${{ (trade.whale_price||0).toFixed(4) }}</span></div>
            <div><span class="label">现价</span><span class="value mono">\${{ (trade.fill_price||0).toFixed(4) }}</span></div>
          </div>
          <div class="modal-row"><span class="label">市值</span><span class="value mono">\${{ (trade.sim_usd||0).toFixed(2) }}</span></div>
          <div class="modal-row" v-if="trade.pnl_realized">
            <span class="label">浮动盈亏</span>
            <span class="value mono" :class="trade.pnl_realized>=0?'green':'red'">{{ trade.pnl_realized>=0?'+':'' }}\${{ trade.pnl_realized.toFixed(4) }}</span>
          </div>
        </div>
      </div>
      <div class="modal-section" v-else>
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
  data(){ return { chartData: [], tooltip: { visible: false, x: 0, y: 0, label: '', value: '' } }; },
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
      const s=this.trade?this.trade.status:''; if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; if(s==='POSITION')return'持仓中'; return'失败';
    }
  },
  watch: {
    trade: {
      immediate: true,
      async handler(t){
        this.tooltip.visible = false;
        if(!t||!t.slug) return;
        try {
          const r = await fetch('/api/market/'+encodeURIComponent(t.slug)+'/trades');
          const data = await r.json();
          this.chartData = data.points || [];
          this.$nextTick(()=> this.drawChart());
        } catch(e){ console.error('chart:',e); }
      }
    }
  },
  methods: {
    isPosition(){ return this.trade&&this.trade.status==='POSITION'; },
    drawChart(){
      const canvas = this.$refs.chart;
      if(!canvas||!this.chartData.length) return;
      const dpr = window.devicePixelRatio||1;
      const rect = canvas.parentElement.getBoundingClientRect();
      const W = rect.width;
      const H = 220;
      canvas.width = W*dpr; canvas.height = H*dpr;
      canvas.style.width = W+'px'; canvas.style.height = H+'px';
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr,dpr);

      // Collect unique Yes-prices sorted by time
      const seen=new Set();
      const pts=[];
      for(const p of this.chartData){
        if(p.o==='Yes'||p.o==='Up'){
          const k=p.t+'_'+p.p.toFixed(4);
          if(seen.has(k)) continue; seen.add(k);
          pts.push({t:p.t, v:p.p});
        }
      }
      pts.sort((a,b)=>a.t-b.t);
      if(pts.length<2) return;

      const pad={t:24,r:24,b:40,l:44};
      const pw=W-pad.l-pad.r;
      const ph=H-pad.t-pad.b;
      const tMin=pts[0].t, tMax=pts[pts.length-1].t;
      const tRange=tMax-tMin||1;
      const vMin=0, vMax=1;

      const tx=t=>(t-tMin)/tRange*pw+pad.l;
      const ty=v=>pad.t+ph-(v-vMin)/(vMax-vMin)*ph;

      // Gradient fill
      const grad=ctx.createLinearGradient(0,pad.t,0,H-pad.b);
      grad.addColorStop(0,'rgba(0,230,118,0.18)');
      grad.addColorStop(1,'rgba(0,230,118,0.01)');

      // Draw area fill
      ctx.beginPath();
      ctx.moveTo(tx(pts[0].t),H-pad.b);
      for(const p of pts) ctx.lineTo(tx(p.t),ty(p.v));
      ctx.lineTo(tx(pts[pts.length-1].t),H-pad.b);
      ctx.closePath();
      ctx.fillStyle=grad;
      ctx.fill();

      // Draw line
      ctx.beginPath();
      ctx.moveTo(tx(pts[0].t),ty(pts[0].v));
      for(let i=1;i<pts.length;i++){
        const x0=tx(pts[i-1].t),y0=ty(pts[i-1].v);
        const x1=tx(pts[i].t),y1=ty(pts[i].v);
        const cx=(x0+x1)/2;
        ctx.bezierCurveTo(cx,y0,cx,y1,x1,y1);
      }
      ctx.strokeStyle='#00e676';
      ctx.lineWidth=2;
      ctx.stroke();

      // Y-axis labels
      ctx.fillStyle='#5a6b7d';
      ctx.font='10px JetBrains Mono,monospace';
      ctx.textAlign='right';
      for(let v=0;v<=1;v+=0.25){
        ctx.fillText(Math.round(v*100)+'%',pad.l-6,ty(v)+4);
      }

      // X-axis labels
      ctx.textAlign='center';
      const labelCount=Math.min(6,pts.length);
      for(let i=0;i<labelCount;i++){
        const idx=Math.floor(i*(pts.length-1)/(labelCount-1));
        const d=new Date(pts[idx].t*1000);
        const lbl=(d.getMonth()+1)+'/'+d.getDate();
        ctx.fillText(lbl,tx(pts[idx].t),H-12);
      }

      // Grid lines
      ctx.strokeStyle='rgba(28,40,56,0.6)';
      ctx.lineWidth=0.5;
      for(let v=0.25;v<=1;v+=0.25){
        ctx.beginPath(); ctx.moveTo(pad.l,ty(v)); ctx.lineTo(W-pad.r,ty(v)); ctx.stroke();
      }

      // Mouse tracking
      const self=this;
      canvas.onmousemove=function(e){
        const mx=e.offsetX;
        let nearest=pts[0],minDist=Infinity;
        for(const p of pts){ const d=Math.abs(tx(p.t)-mx); if(d<minDist){minDist=d;nearest=p;} }
        const x=tx(nearest.t),y=ty(nearest.v);
        const d=new Date(nearest.t*1000);
        self.tooltip={
          visible:true,
          x:Math.min(x,W-130),
          y:Math.max(y-50,0),
          label:(d.getMonth()+1)+'/'+d.getDate()+' '+d.getHours()+':'+String(d.getMinutes()).padStart(2,'0'),
          value:(nearest.v*100).toFixed(1)+'%'
        };
        // Redraw dot
        self.drawChart();
        const c2=canvas.getContext('2d'); c2.scale(dpr,dpr);
        c2.beginPath(); c2.arc(x,y,4,0,Math.PI*2); c2.fillStyle='#00e676'; c2.fill();
        c2.beginPath(); c2.arc(x,y,8,0,Math.PI*2); c2.strokeStyle='rgba(0,230,118,0.3)'; c2.lineWidth=2; c2.stroke();
      };
      canvas.onmouseleave=function(){ self.tooltip.visible=false; self.drawChart(); };
    }
  }
};
