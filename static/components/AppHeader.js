export default {
  template: `
  <header>
    <h1>◆ Polymarket 跟单监控面板</h1>
    <div class="sub">
      <span><span class="pulse"></span>实时监控中</span>
      <span class="muted" style="font-size:11px;">{{ clock }}</span>
      <span class="muted" style="font-size:11px;">监控中: {{ walletCount }} 个钱包</span>
    </div>
  </header>`,
  props: { walletCount: { type: Number, default: 0 } },
  data() { return { clock: '' }; },
  mounted() {
    this.updateClock();
    this._timer = setInterval(() => this.updateClock(), 1000);
  },
  beforeUnmount() { clearInterval(this._timer); },
  methods: {
    updateClock() { this.clock = new Date().toLocaleString('zh-CN', { hour12: false }); }
  }
};
