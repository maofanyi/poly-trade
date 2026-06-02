export default {
  template: `<tr>
    <td><span v-if="monitoring" style="color:var(--green);font-weight:700;">● 监控中</span><span v-else style="color:var(--muted);">○</span></td>
    <td style="font-weight:600;">{{ wallet.name }}</td>
    <td class="addr" :title="wallet.addr">{{ wallet.addr.slice(0,6) }}...{{ wallet.addr.slice(-4) }}</td>
    <td><span class="cat-tag" :class="catClass">{{ catName }}</span></td>
    <td>{{ wallet.winRate||'—' }}</td>
    <td class="green">{{ wallet.profit||'—' }}</td>
    <td>
      <button v-if="!monitoring" class="btn" @click="$emit('add',wallet.addr,wallet.name,wallet.cat)">+ 添加跟单</button>
      <button v-else class="btn danger" @click="$emit('remove',wallet.name)">移除</button>
    </td>
  </tr>`,
  props: { wallet:{ type:Object, required:true }, monitoring:{ type:Boolean, default:false } },
  emits: ['add','remove'],
  computed: { catClass(){ return (this.wallet.cat||'W')[0].toLowerCase(); }, catName(){ const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[this.wallet.cat]||this.wallet.cat; } }
};
