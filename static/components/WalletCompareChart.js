export default {
  template: `
  <div class="card" style="padding:14px;margin-bottom:12px;">
    <div class="section-title" style="margin-top:0;">📊 钱包对比</div>
    <div v-if="series.length === 0" class="muted" style="text-align:center;padding:20px;">暂无P&L数据</div>
    <div ref="chart" style="width:100%;height:360px;" v-show="series.length > 0"></div>
  </div>`,
  data(){ return { series: [], chart: null }; },
  async mounted(){
    try {
      const r = await fetch('/api/summary/compare');
      if(!r.ok) return;
      this.series = await r.json();
      this.$nextTick(() => this.render());
    } catch(e){}
    window.addEventListener('resize', () => this.chart?.resize());
  },
  methods: {
    render(){
      if(!this.$refs.chart || !this.series.length) return;
      import('echarts').then(echarts => {
        this.chart = echarts.init(this.$refs.chart, 'dark');
        const colors = ['#00e676','#448aff','#ffab00','#ff3d4f','#bb86fc','#03dac6','#ff7597','#64ffda'];
        this.chart.setOption({
          backgroundColor: 'transparent',
          tooltip: { trigger: 'axis', valueFormatter: v => (v??0).toFixed(1)+'%' },
          legend: { bottom: 0, textStyle: { color: '#5a6b7d', fontSize: 10 }, data: this.series.map(s => s.name) },
          grid: { left: 50, right: 20, top: 10, bottom: 40 },
          xAxis: { type: 'category', data: this.series[0]?.points.map(p => p.t) || [], axisLabel: { color: '#5a6b7d', fontSize: 9, rotate: 30, interval: 'auto' } },
          yAxis: { type: 'value', axisLabel: { color: '#5a6b7d', formatter: v => v.toFixed(0)+'%' }, splitLine: { lineStyle: { color: '#1c2838' } } },
          series: this.series.map((s, i) => ({
            name: s.name, type: 'line',
            data: s.points.map(p => p.v),
            lineStyle: { color: colors[i%colors.length], width: 1.5 },
            itemStyle: { color: colors[i%colors.length] },
            symbol: 'none', smooth: true,
          }))
        }, true);
      });
    }
  }
};
