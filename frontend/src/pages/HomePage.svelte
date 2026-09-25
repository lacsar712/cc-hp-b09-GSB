<script>
  import { onMount } from 'svelte'
  import { role } from '../lib/auth'
  import { api } from '../lib/api'

  let rows = $state([])
  let herb = $state('白芍')
  let tempC = $state(110)
  let minutes = $state(10)
  let error = $state('')

  async function load() {
    rows = await api('/api/batches')
  }

  async function save() {
    error = ''
    try {
      await api('/api/batches', {
        method: 'POST',
        body: JSON.stringify({
          herb,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
        }),
      })
      await load()
    } catch (err) {
      error = err.message
    }
  }

  onMount(load)
</script>

<div class="card-box">
  <h2>现场记录台</h2>
  <p class="muted">这里是首页的一张卡，不属于处方汇总专页。清炒温度 80–150、时长 5–30 分钟方可放行。</p>
  {#if $role === 'writer'}
    <input bind:value={herb} placeholder="饮片" />
    <input type="number" bind:value={tempC} title="温度℃" placeholder="温度℃" />
    <input type="number" bind:value={minutes} title="时长(分)" placeholder="时长(分)" />
    <button onclick={save}>写入清炒记录</button>
    {#if error}<p class="error">{error}</p>{/if}
  {:else}
    <p class="muted">质检员只读：不可写入。</p>
  {/if}
</div>

<div class="card-box">
  <h2>全部批次</h2>
  <ul>
    {#each rows as row (row.id)}
      <li>
        {row.herb} ·
        <span class="tag" class:ok={row.verdict === '放行'} class:no={row.verdict !== '放行'}>{row.verdict}</span>
        · {row.reason} · 温度 {row.doc.steps[0]?.temp_c}
        {#if row.card_id}<span class="muted">（处方卡 #{row.card_id}）</span>{/if}
      </li>
    {/each}
  </ul>
</div>
