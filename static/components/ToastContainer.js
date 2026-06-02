export default {
  template: `<div style="position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:6px;">
    <div v-for="(t,i) in toasts" :key="i" :style="{background:'var(--card)',border:'1px solid '+t.color,padding:'8px 14px',borderRadius:'6px',fontSize:'12px',maxWidth:'320px',transition:'opacity 0.3s'}">{{ t.message }}</div>
  </div>`,
  props: { alerts:{ type:Array, default:()=>[] } },
  data(){ return { toasts:[] }; },
  watch: { alerts:{ handler(a){ for(const x of a){ const c=x.alert_type==='wallet_loss'?'var(--red)':'var(--amber)'; this.toasts.push({message:x.message,color:c}); setTimeout(()=>this.toasts.shift(),4000); } }, deep:true } }
};
