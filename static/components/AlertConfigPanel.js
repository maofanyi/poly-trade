export default {
  template: `<div class="card" style="padding:14px;margin-bottom:12px;">
    <div class="section-title" style="margin-top:0;">⚙️ 告警配置</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
      <div><label class="muted" style="font-size:11px;">启用告警</label><br><input type="checkbox" v-model="config.enabled" @change="save"></div>
      <div><label class="muted" style="font-size:11px;">亏损阈值 (%)</label><br><input class="search-input" type="number" v-model.number="config.pnl_threshold_pct" @change="save" style="max-width:100px;"></div>
      <div><label class="muted" style="font-size:11px;">单笔亏损上限 (\$)</label><br><input class="search-input" type="number" v-model.number="config.single_loss_usd" @change="save" style="max-width:100px;"></div>
      <div><label class="muted" style="font-size:11px;">通知方式</label><br><select v-model="config.webhook_type" @change="save" class="search-input" style="max-width:120px;"><option value="">仅仪表盘</option><option value="bark">Bark</option><option value="telegram">Telegram</option><option value="wecom">企业微信</option></select></div>
    </div>
    <div v-if="config.webhook_type" style="margin-top:8px;"><label class="muted" style="font-size:11px;">Webhook URL</label><br><input class="search-input" v-model="config.webhook_url" @change="save" style="max-width:100%;" placeholder="https://..."></div>
  </div>`,
  data(){ return { config:{enabled:true,pnl_threshold_pct:-20,single_loss_usd:10,webhook_type:'',webhook_url:''} }; },
  async mounted(){ try{ const resp=await fetch('/api/alerts'); if(resp.ok)this.config=await resp.json(); }catch(e){} },
  methods: { async save(){ try{ await fetch('/api/alerts',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(this.config)}); }catch(e){} } }
};
