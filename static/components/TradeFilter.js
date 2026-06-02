export default {
  template: `<div class="filter-bar">
    <button class="filter-btn" :class="{active:active==='all'}" @click="set('all')">全部</button>
    <button class="filter-btn" :class="{active:active==='today'}" @click="set('today')">今日</button>
    <button class="filter-btn" :class="{active:active==='week'}" @click="set('week')">本周</button>
    <button class="filter-btn" :class="{active:active==='month'}" @click="set('month')">本月</button>
  </div>`,
  emits: ['filter'],
  data() { return { active: 'all' }; },
  methods: { set(f) { this.active = f; this.$emit('filter', f); } }
};
