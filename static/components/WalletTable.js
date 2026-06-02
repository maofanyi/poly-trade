import WalletRow from './WalletRow.js';
export default {
  components: { WalletRow },
  template: `<div>
    <div class="filter-bar" style="margin-bottom:10px;">
      <input class="search-input" v-model="search" placeholder="搜索钱包名称或地址...">
      <button v-for="c in categories" class="filter-btn" :class="{active:catFilter===c}" @click="catFilter=c">{{ c === 'all' ? '全部' : catName(c) }}</button>
    </div>
    <div class="table-wrap"><table><thead><tr><th>状态</th><th>钱包</th><th>地址</th><th>类别</th><th>胜率</th><th>盈利</th><th>操作</th></tr></thead>
    <tbody>
      <wallet-row v-for="w in filtered" :key="w.addr" :wallet="w" :monitoring="activeNames.has(w.name)" @add="addWallet" @remove="removeWallet" />
      <tr v-if="filtered.length===0"><td colspan="7"><div class="empty">无匹配结果</div></td></tr>
    </tbody></table></div>
  </div>`,
  props: { candidates:{ type:Array, default:()=>[] }, activeNames:{ type:Set, default:()=>new Set() } },
  emits: ['add','remove'],
  data(){ return { search:'', catFilter:'all', categories:['all','Weather','Politics','Sports','Tech','Culture'] }; },
  computed: { filtered(){ let a=this.candidates; if(this.catFilter!=='all')a=a.filter(w=>w.cat===this.catFilter); const s=this.search.toLowerCase(); if(s)a=a.filter(w=>w.name.toLowerCase().includes(s)||w.addr.toLowerCase().includes(s)); return a; } },
  methods: {
    catName(c){ const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[c]||c; },
    addWallet(addr,name,cat){ this.$emit('add',addr,name,cat); },
    removeWallet(name){ this.$emit('remove',name); }
  }
};
