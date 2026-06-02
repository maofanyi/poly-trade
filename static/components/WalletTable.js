import WalletRow from './WalletRow.js';
export default {
  components: { WalletRow },
  template: `<div>
    <!-- Manual address input -->
    <div class="card" style="padding:12px;margin-bottom:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
      <span class="muted" style="font-size:12px;white-space:nowrap;">🔗 输入地址:</span>
      <input class="search-input" v-model="addrInput" placeholder="0x..." style="flex:1;min-width:250px;max-width:420px;" @keyup.enter="validateAddr">
      <button class="btn" @click="validateAddr" :disabled="validating">
        {{ validating ? '验证中...' : '验证' }}
      </button>
      <span v-if="validResult && validResult.valid && !validResult.already_added" style="font-size:12px;color:var(--green);">
        ✓ {{ validResult.name }} | {{ validResult.trades_found }}筆交易
        <button class="btn" @click="addCustom" style="margin-left:8px;">+ 添加跟单</button>
      </span>
      <span v-if="validResult && validResult.valid && validResult.already_added" style="font-size:12px;color:var(--amber);">
        已在列表中: {{ validResult.name }}
      </span>
      <span v-if="validResult && !validResult.valid" style="font-size:12px;color:var(--red);">
        ✗ {{ validResult.message }}
      </span>
    </div>
    <!-- Filter -->
    <div class="filter-bar" style="margin-bottom:10px;">
      <input class="search-input" v-model="search" placeholder="搜索钱包名称或地址...">
      <button v-for="c in categories" class="filter-btn" :class="{active:catFilter===c}" @click="catFilter=c">{{ c === 'all' ? '全部' : catName(c) }}</button>
    </div>
    <div class="table-wrap"><table><thead><tr><th>状态</th><th>钱包</th><th>地址</th><th>类别</th><th>评分</th><th>交易数</th><th>操作</th></tr></thead>
    <tbody>
      <wallet-row v-for="w in enriched" :key="w.addr" :wallet="w" :monitoring="activeNames.has(w.name)" @add="addWallet" @remove="removeWallet" />
      <tr v-if="enriched.length===0"><td colspan="7"><div class="empty">无匹配结果</div></td></tr>
    </tbody></table></div>
  </div>`,
  props: { candidates:{ type:Array, default:()=>[] }, activeNames:{ type:Set, default:()=>new Set() }, scores:{ type:Array, default:()=>[] } },
  emits: ['add','remove','validate'],
  data(){ return {
    search:'', catFilter:'all', categories:['all','Weather','Politics','Sports','Tech','Culture'],
    addrInput:'', validating:false, validResult:null
  }; },
  computed: {
    scoreMap(){ const m={}; for(const s of this.scores){ m[s.address]=s; if(!this.candidates.find(c=>c.addr===s.address)&&!m[s.address]){} } return m; },
    enriched(){
      return this.candidates.map(w => {
        const s = this.scoreMap[w.addr];
        return s ? { ...w, scoreObj: s, winRate: s.score, profit: s.trades+'筆' } : w;
      });
    },
    filtered(){
      let a=this.enriched;
      if(this.catFilter!=='all')a=a.filter(w=>w.cat===this.catFilter);
      const s=this.search.toLowerCase();
      if(s)a=a.filter(w=>w.name.toLowerCase().includes(s)||w.addr.toLowerCase().includes(s));
      return a;
    }
  },
  methods: {
    catName(c){ const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[c]||c; },
    addWallet(addr,name,cat){ this.$emit('add',addr,name,cat); },
    removeWallet(name){ this.$emit('remove',name); },
    async validateAddr(){
      const addr = this.addrInput.trim();
      if (!addr) return;
      this.validating = true;
      this.validResult = null;
      try {
        const resp = await fetch('/api/wallets/validate', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({address: addr})
        });
        this.validResult = await resp.json();
      } catch(e) {
        this.validResult = { valid:false, message:'网络错误' };
      }
      this.validating = false;
    },
    addCustom(){
      if (this.validResult) {
        this.$emit('add', this.validResult.address, this.validResult.name, this.validResult.category);
        this.validResult = null;
        this.addrInput = '';
      }
    }
  }
};
