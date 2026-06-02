import * as echarts from 'echarts';
export default {
  template: `<div>
    <div class="filter-bar">
      <select v-model="selectedWallet" @change="loadData" class="search-input" style="max-width:200px;"><option value="">选择钱包...</option><option v-for="w in wallets" :key="w.id" :value="w.id">{{ w.name }}</option></select>
      <button class="filter-btn" :class="{active:days===7}" @click="days=7;loadData()">7天</button>
      <button class="filter-btn" :class="{active:days===30}" @click="days=30;loadData()">30天</button>
      <button class="filter-btn" :class="{active:days===90}" @click="days=90;loadData()">90天</button>
    </div>
    <div ref="chart" style="width:100%;height:350px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:12px;"></div>
  </div>`,
  props: { wallets:{ type:Array, default:()=>[] } },
  data(){ return { selectedWallet:'', days:7, chart:null }; },
  mounted(){ this.chart=echarts.init(this.$refs.chart,'dark'); window.addEventListener('resize',()=>this.chart?.resize()); },
  methods: {
    async loadData(){
      if(!this.selectedWallet)return;
      const resp=await fetch(`/api/wallets/${this.selectedWallet}/pnl?days=${this.days}`);
      if(!resp.ok)return;
      const data=await resp.json();
      this.chart.setOption({
        backgroundColor:'transparent', tooltip:{trigger:'axis'},
        grid:{left:50,right:20,top:20,bottom:30},
        xAxis:{type:'category',data:data.map(d=>d.timestamp?.slice(0,10)||''),axisLabel:{color:'#5a6b7d',fontSize:10}},
        yAxis:{type:'value',axisLabel:{color:'#5a6b7d'},splitLine:{lineStyle:{color:'#1c2838'}}},
        series:[{type:'line',data:data.map(d=>d.pnl||0),lineStyle:{color:'#00e676',width:2},itemStyle:{color:'#00e676'},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(0,230,118,0.15)'},{offset:1,color:'rgba(0,230,118,0)'}])},smooth:true}]
      },true);
    }
  }
};
