<script>
  import { api } from '../lib/api.js'

  let { role, onLogout } = $props()
  let rows = $state([])
  let herb = '白芍'
  let tempC = 110
  let minutes = 10
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

  load()
</script>

<section class="page">
  <h2>炮制记录</h2>
  <p class="hint">炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>

  {#if role === 'writer'}
    <div class="write-bar">
      <input bind:value={herb} placeholder="饮片" />
      <input type="number" bind:value={tempC} title="温度℃" />
      <input type="number" bind:value={minutes} title="时长(分)" />
      <button on:click={save}>写入清炒记录</button>
    </div>
    {#if error}<p class="error">{error}</p>{/if}
  {/if}

  <ul class="rows">
    {#each rows as row (row.id)}
      <li>
        <span class="verdict" data-verdict={row.verdict}>{row.verdict}</span>
        {row.herb} · {row.reason} · 温度 {row.doc.steps[0].temp_c}
      </li>
    {/each}
  </ul>
  <button class="ghost" on:click={onLogout}>退出</button>
</section>

<style>
  .page { max-width: 760px; }
  .hint { color: #6b5b4a; }
  .write-bar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
  input { padding: 6px 8px; }
  .rows { list-style: none; padding: 0; }
  .rows li { padding: 8px 0; border-bottom: 1px solid #ecdfd0; }
  .verdict {
    display: inline-block; min-width: 52px; text-align: center;
    padding: 1px 8px; margin-right: 8px; border-radius: 10px; font-size: 13px;
  }
  [data-verdict='放行'] { background: #e4f6e8; color: #1c7a37; }
  [data-verdict='未放行'] { background: #fdeaea; color: #b42318; }
  .error { color: #b42318; }
  .ghost { margin-top: 16px; }
</style>
