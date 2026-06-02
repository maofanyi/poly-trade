# Trade Detail Modal — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Click a trade row to open a rich detail overlay showing full trade information, styled similar to Polymarket's own trade view.

**Architecture:** New Vue component `TradeDetailModal` renders as a fixed overlay. Backend API fetches trade history for price chart. ECharts renders probability lines.

**Tech Stack:** Vue 3 CDN, existing CSS variables, no new dependencies.

---

## Design Reference (Polymarket-like)

```
┌─────────────────────────────────────────────────────┐
│  ✕                                          关闭    │
├─────────────────────────────────────────────────────┤
│  📋 市场信息                                        │
│  ┌─────────────────────────────────────────────────┐│
│  │ 🏷 类别: Weather          📊 状态: 已结算       ││
│  │                                                  ││
│  │ Will the highest temperature in Moscow be 22°C  ││
│  │ on May 24, 2026?                                 ││
│  │                                                  ││
│  │ 结果: No · 结算价 $1.00                          ││
│  └─────────────────────────────────────────────────┘│
│                                                      │
│  🐋 鲸鱼交易                                         │
│  ┌─────────────────────────────────────────────────┐│
│  │  买入  ·  68.78 份  ·  @ $0.9000                ││
│  │  交易额: $61.90                                  ││
│  │  时间: 2026-05-24 11:15 UTC                      ││
│  │  交易Hash: 0x11dd55...fe0d16                     ││
│  └─────────────────────────────────────────────────┘│
│                                                      │
│  📊 模拟跟单                                         │
│  ┌─────────────────────────────────────────────────┐│
│  │  跟单金额: $1.24       成交价: $0.9050           ││
│  │  滑点: 0.56%          状态: 已成交               ││
│  │  盈亏: +$0.12                                    ││
│  └─────────────────────────────────────────────────┘│
│                                                      │
│  🔗 链接                                            │
│  ┌─────────────────────────────────────────────────┐│
│  │  Polymarket 市场  ·  Polygonscan 交易            ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

---

## Files

| File | Action |
|------|--------|
| `static/components/TradeDetailModal.js` | Create — modal component |
| `static/components/TradeCard.js` | Modify — emit `detail` event on click |
| `static/index.html` | Modify — add modal CSS + mount point |

---

## Task 1: Create TradeDetailModal component

### `static/components/TradeDetailModal.js`

```javascript
export default {
  template: `
  <div v-if="trade" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <span class="modal-title">📋 交易详情</span>
        <button class="modal-close" @click="$emit('close')">✕</button>
      </div>

      <!-- Market Info -->
      <div class="modal-section">
        <div class="modal-section-title">市场信息</div>
        <div class="modal-card">
          <div class="modal-meta">
            <span class="cat-tag" :class="catClass">{{ catName }}</span>
            <span v-if="isExpired" class="resolved-badge" style="font-size:10px;">已结算</span>
            <span v-else class="resolved-badge" style="font-size:10px;background:rgba(0,230,118,0.12);color:var(--green);">交易中</span>
          </div>
          <div class="modal-market-title">{{ trade.slug || '—' }}</div>
          <div v-if="isExpired" class="modal-resolution">
            结果: <strong>{{ trade.outcome || '—' }}</strong>
          </div>
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
      const s=this.trade?this.trade.status:'';
      if(s==='FILLED')return'status-filled';
      if(s==='SKIPPED')return'status-skipped';
      return'status-failed';
    },
    statusLabel(){
      const s=this.trade?this.trade.status:'';
      if(s==='FILLED')return'已成交';
      if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过';
      return'失败';
    }
  }
};
```

---

## Task 2: Update TradeCard to emit detail event

In `static/components/TradeCard.js`:

Replace the `@click="toggle(t.id)"` on the trade row with `@click="$emit('detail', t)"`. Remove the expand/collapse logic (the modal replaces it).

```javascript
// In template: change @click="toggle(t.id)" to @click="$emit('detail', t)"
// Remove the trade-detail expandable div (lines 20-32)
// Remove data(){ return { expanded: null }; }
// Remove toggle method
// Keep isExpired, slipPct, slipClass, statusClass, statusLabel, rowTitle
```

Add `emits: ['remove','detail']`.

---

## Task 3: Wire modal in app.js and index.html

### In `static/app.js`:

Add import:
```javascript
import TradeDetailModal from './components/TradeDetailModal.js';
```

Add registration:
```javascript
app.component('TradeDetailModal', TradeDetailModal);
```

Add to setup:
```javascript
const detailTrade = ref(null);
const detailWalletCat = ref('');
function showTradeDetail(trade, cat) {
  detailTrade.value = trade;
  detailWalletCat.value = cat;
}
```

Add to return: `detailTrade, detailWalletCat, showTradeDetail`

### In `static/index.html`:

In the TradeList section (monitor tab), add `@detail` handler:

```html
<trade-list :trades="filteredTrades" :wallets="wallets" @remove="removeWallet" @detail="(trade, cat) => { detailTrade=trade; detailWalletCat=cat||''; }"></trade-list>
```

Add modal at the bottom of the body:
```html
<trade-detail-modal v-if="detailTrade" :trade="detailTrade" :wallet-cat="detailWalletCat" @close="detailTrade=null"></trade-detail-modal>
```

---

## Task 4: Add modal CSS

In `static/index.html` `<style>` section, add before `</style>`:

```css
/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; display: flex; align-items: flex-start; justify-content: center; padding-top: 40px; overflow-y: auto; }
.modal-panel { background: var(--card); border: 1px solid var(--border); border-radius: 12px; width: 520px; max-width: 95vw; margin-bottom: 40px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border); }
.modal-title { font-weight: 700; font-size: 14px; }
.modal-close { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 18px; padding: 4px 8px; }
.modal-close:hover { color: var(--text); }
.modal-section { padding: 0 18px; margin: 14px 0; }
.modal-section-title { font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }
.modal-card { background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; }
.modal-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.modal-market-title { font-size: 13px; font-weight: 600; line-height: 1.5; margin-bottom: 6px; word-break: break-all; }
.modal-resolution { font-size: 11px; color: var(--amber); margin-top: 4px; }
.modal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.modal-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 12px; }
.modal-row .label { color: var(--muted); font-size: 11px; }
.modal-row .value, .modal-grid .value { text-align: right; font-size: 12px; }
.modal-grid .label { color: var(--muted); font-size: 10px; display: block; margin-bottom: 2px; }
.modal-grid .value { font-size: 13px; font-weight: 600; }

@media(max-width:560px) {
  .modal-panel { width: 100%; border-radius: 0; }
  .modal-grid { grid-template-columns: 1fr 1fr; }
}
```

---

---

## Task 5: Market price chart in modal

### Backend: `api/state.py` — add trade history endpoint

```python
@router.get("/market/{slug}/trades")
def get_market_trades(slug: str, limit: int = 50):
    """Get recent trades for a market (for price chart)."""
    import urllib.request, json as _json
    url = f"https://data-api.polymarket.com/trades?slug={urllib.parse.quote(slug)}&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        trades = _json.loads(resp.read())
    # Return simplified data for charting
    points = []
    for t in (trades or []):
        points.append({
            "t": int(t.get("timestamp", 0)),
            "p": float(t.get("price", 0)),
            "o": t.get("outcome", ""),
        })
    return {"slug": slug, "points": points}
```

### Frontend: Add chart section to TradeDetailModal

In the modal component, add after Market Info section:

```html
<!-- Price Chart -->
<div class="modal-section">
  <div class="modal-section-title">📈 价格走势</div>
  <div class="modal-card" style="padding:0;">
    <div ref="chart" style="height:200px;width:100%;"></div>
  </div>
</div>
```

Add data and methods for chart:
```javascript
data(){ return { chartData: null, chart: null }; },
async mounted(){},
watch: {
  trade: {
    immediate: true,
    async handler(t){
      if(!t||!t.slug) return;
      try {
        const r = await fetch('/api/market/'+encodeURIComponent(t.slug)+'/trades');
        this.chartData = await r.json();
        this.$nextTick(()=> this.renderChart());
      } catch(e){}
    }
  }
},
methods: {
  renderChart(){
    if(!this.chartData || !this.$refs.chart) return;
    const points = this.chartData.points || [];
    // Group by outcome and sort by time
    const yesData = [], noData = [];
    for(const p of points){
      const dt = new Date(p.t*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
      if(p.o==='Yes'||p.o==='Up') yesData.push([dt, p.p]);
      else noData.push([dt, 1-p.p]);
    }
    // Sort by time
    yesData.sort((a,b)=>a[0].localeCompare(b[0]));
    noData.sort((a,b)=>a[0].localeCompare(b[0]));
    
    import('echarts').then(echarts=>{
      const c = echarts.init(this.$refs.chart, 'dark');
      c.setOption({
        backgroundColor:'transparent',
        tooltip:{trigger:'axis'},
        grid:{left:45,right:15,top:10,bottom:25},
        xAxis:{type:'category',data:yesData.map(d=>d[0]),axisLabel:{color:'#5a6b7d',fontSize:9,rotate:30}},
        yAxis:{type:'value',min:0,max:1,axisLabel:{color:'#5a6b7d',formatter:v=>(v*100).toFixed(0)+'%'},splitLine:{lineStyle:{color:'#1c2838'}}},
        series:[
          {name:'Yes',type:'line',data:yesData.map(d=>d[1]),lineStyle:{color:'#00e676',width:1.5},itemStyle:{color:'#00e676'},symbol:'none',smooth:true},
          {name:'No',type:'line',data:noData.map(d=>d[1]),lineStyle:{color:'#ff3d4f',width:1.5},itemStyle:{color:'#ff3d4f'},symbol:'none',smooth:true}
        ]
      },true);
    });
  }
}
```

---

## Implementation Order

Task 5 (API + chart) → Task 1 (modal component) → Task 2 (update TradeCard) → Task 3 (wire) → Task 4 (CSS)

4 files modified, 1 new file. Backend: 1 new endpoint.
