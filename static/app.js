import { createApp, ref, computed, onMounted } from 'vue';
import { useWebSocket } from './composables/useWebSocket.js';
import AppHeader from './components/AppHeader.js';
import SummaryBar from './components/SummaryBar.js';
import PnlCardGrid from './components/PnlCardGrid.js';
import TradeFilter from './components/TradeFilter.js';
import TradeList from './components/TradeList.js';
import WalletTable from './components/WalletTable.js';
import PnlTrendChart from './components/PnlTrendChart.js';
import AlertConfigPanel from './components/AlertConfigPanel.js';
import ToastContainer from './components/ToastContainer.js';

const API = '/api';

const app = createApp({
  setup() {
    const activeTab = ref('monitor');
    const currentFilter = ref('all');
    const wallets = ref([]);
    const trades = ref([]);
    const summary = ref({});
    const pnlHistory = ref([]);
    const connected = ref(false);
    const activeNames = ref(new Set());
    const alerts = ref([]);

    async function loadState() {
      try {
        const resp = await fetch(`${API}/state?t=${Date.now()}`);
        if (resp.ok) {
          const data = await resp.json();
          wallets.value = data.wallets || [];
          trades.value = data.trades || [];
          summary.value = data.summary || {};
          activeNames.value = new Set((data.wallets || []).map(w => w.name));
        }
      } catch (e) { console.error('loadState:', e); }
    }

    const { connect } = useWebSocket({
      onMessage(msg) {
        switch (msg.type) {
          case 'pnl_update':
            for (const update of (msg.wallets || [])) {
              const idx = wallets.value.findIndex(w => w.name === update.name);
              if (idx >= 0) wallets.value[idx] = { ...wallets.value[idx], ...update };
            }
            break;
          case 'new_trade':
            if (msg.trade) trades.value.unshift(msg.trade);
            break;
          case 'alert':
            alerts.value.push(msg);
            break;
          case 'wallet_changed':
            loadState();
            break;
        }
      },
      onOpen() { connected.value = true; loadState(); },
      onClose() { connected.value = false; setTimeout(() => connect(), 3000); }
    });

    const filteredTrades = computed(() => {
      let result = trades.value.filter(t => t.status === 'FILLED');
      if (currentFilter.value === 'today') {
        const today = new Date().toDateString();
        result = result.filter(t => new Date(t.timestamp).toDateString() === today);
      } else if (currentFilter.value === 'week') {
        const d = new Date();
        const ws = new Date(d.getFullYear(), d.getMonth(), d.getDate() - d.getDay());
        result = result.filter(t => new Date(t.timestamp) >= ws);
      } else if (currentFilter.value === 'month') {
        const ms = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
        result = result.filter(t => new Date(t.timestamp) >= ms);
      }
      return result;
    });

    const sortedPnl = computed(() =>
      [...wallets.value]
        .filter(w => w.pnl_pct != null)   // only wallets with trading activity
        .sort((a, b) => (b.pnl_pct || 0) - (a.pnl_pct || 0))
    );

    const inactiveWallets = computed(() =>
      [...wallets.value].filter(w => w.pnl_pct == null)
    );

    async function addWallet(addr, name, cat) {
      try {
        await fetch(`${API}/wallets`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: addr, name, category: cat }) });
        await loadState();
      } catch (e) { console.error(e); }
    }

    async function removeWallet(name) {
      const w = wallets.value.find(w => w.name === name);
      if (!w) return;
      try {
        await fetch(`${API}/wallets/${w.id}`, { method: 'DELETE' });
        await loadState();
      } catch (e) { console.error(e); }
    }

    const candidates = ref([
      {name:'HondaCivic',addr:'0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa',cat:'Weather',winRate:'85.7%',profit:'$48K'},
      {name:'ikik111',addr:'0x57ee70867b4e387de9de34fd62bc685aa02a8112',cat:'Weather',winRate:'—',profit:'$50K'},
      {name:'Maskache2',addr:'0x1f66796b45581868376365aef54b51eb84184c8d',cat:'Weather',winRate:'30%',profit:'$27K'},
      {name:'JoeTheMeteorologist',addr:'0x1838cca016850ac7185a9b149fe7d0bd2d6629b4',cat:'Weather',winRate:'—',profit:'$77K'},
      {name:'BeefSlayer',addr:'0x331bf91c132af9d921e1908ca0979363fc47193f',cat:'Weather',winRate:'67%',profit:'$49K'},
      {name:'Varyage',addr:'0xd75d96a23515172778d3281f53c9180b985100c8',cat:'Weather',winRate:'78%',profit:'—'},
      {name:'wokerjoesleeper',addr:'0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f',cat:'Politics',winRate:'81%',profit:'$900K'},
      {name:'Frank0951',addr:'0x40471b34671887546013ceb58740625c2efe7293',cat:'Politics',winRate:'62.8%',profit:'$290K'},
      {name:'cowcat',addr:'0x38e59b36aae31b164200d0cad7c3fe5e0ee795e7',cat:'Politics',winRate:'>88%',profit:'$200K'},
      {name:'ScottyNooo',addr:'0xbacd00c9080a82ded56f504ee8810af732b0ab35',cat:'Politics',winRate:'58.8%',profit:'$1.3M'},
      {name:'HowDareYou',addr:'0x4bbe10ba5b7f6df147c0dae17b46c44a6e562cf3',cat:'Politics',winRate:'100%',profit:'$277K'},
      {name:'ewelmealt',addr:'0x07921379f7b31ef93da634b688b2fe36897db778',cat:'Sports',winRate:'~100%',profit:'$900K'},
      {name:'EFFICIENCYEXPERT',addr:'0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5',cat:'Sports',winRate:'—',profit:'$580K'},
      {name:'middleoftheocean',addr:'0x6c743aafd813475986dcd930f380a1f50901bd4e',cat:'Sports',winRate:'83.1%',profit:'$470K'},
      {name:'synnet',addr:'0x8e0b7ae246205b1ddf79172148a58a3204139e5c',cat:'Sports',winRate:'—',profit:'$290K'},
      {name:'CKW',addr:'0x92672c80d36dcd08172aa1e51dface0f20b70f9a',cat:'Sports',winRate:'—',profit:'—'},
      {name:'GeorgeSmiley',addr:'0x2110ba2a1e18840109482ff4ddc547baeff45850',cat:'Tech',winRate:'76.1%',profit:'—'},
      {name:'Optimus',addr:'0xd5b97d08ec6098407bfbf66c2786ccc9967fe44e',cat:'Tech',winRate:'>60%',profit:'$73K'},
      {name:'BobInvestments',addr:'0x41816fc1ebdfeb33f6356f2655ab499253b3de86',cat:'Tech',winRate:'75%',profit:'—'},
      {name:'DerDon',addr:'0xf797d4d1c038d1eb0593edae0e66bf8e4b2e0bf',cat:'Tech',winRate:'75%',profit:'$38K'},
      {name:'Mujurry',addr:'0x5ecde7348ea5100af4360dd7a6e0a3fb1d420787',cat:'Tech',winRate:'>80%',profit:'$170K'},
      {name:'BigChungus',addr:'0x06dcaa14f57d8a0573f5dc5940565e6de667af59',cat:'Culture',winRate:'73.7%',profit:'—'},
      {name:'TheRedChip',addr:'0xdf6da574f8b0c0ce5e01ddb1c5a49b87993e9c5c',cat:'Culture',winRate:'45%',profit:'$100K'},
      {name:'GUHHH',addr:'0x033dc6e3e3e0a3ae55402576990392ae910aaf05',cat:'Culture',winRate:'77.9%',profit:'—'},
      {name:'BeN',addr:'0x668d85d791049bf0100e557a72c7ed4dc97297d2',cat:'Culture',winRate:'67.3%',profit:'—'},
      {name:'pol76',addr:'0x36e7e560c4d4cf32926906d939a18cf91f8a0b6b',cat:'Culture',winRate:'72.9%',profit:'—'},
    ]);

    // Wallet scores (dynamic, refreshed periodically)
    const walletScores = ref([]);

    async function loadScores() {
      try {
        const resp = await fetch(`${API}/wallets/scores`);
        if (resp.ok) walletScores.value = await resp.json();
      } catch (e) {}
    }

    onMounted(() => { loadState(); loadScores(); connect(); });

    function catLabel(c) { const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[c]||c||'—'; }

    return { activeTab, currentFilter, wallets, trades, summary, filteredTrades, sortedPnl, inactiveWallets, pnlHistory, connected, activeNames, alerts, candidates, walletScores, catLabel, addWallet, removeWallet };
  }
});

app.component('AppHeader', AppHeader);
app.component('SummaryBar', SummaryBar);
app.component('PnlCardGrid', PnlCardGrid);
app.component('TradeFilter', TradeFilter);
app.component('TradeList', TradeList);
app.component('WalletTable', WalletTable);
app.component('PnlTrendChart', PnlTrendChart);
app.component('AlertConfigPanel', AlertConfigPanel);
app.component('ToastContainer', ToastContainer);

app.mount('#app');
