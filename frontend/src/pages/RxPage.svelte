<script>
  import { api, fmtTime } from '../lib/api.js'

  let { role } = $props()

  let cards = $state([])
  let notice = $state('')
  let busy = $state(false)

  // 建卡区
  let title = $state('')
  let draftItems = $state([{ herb: '甘草', grams: 100 }])

  // 卡内每味临时写入参数
  let tempByItem = $state({})
  let minByItem = $state({})

  async function load() {
    cards = await api('/api/rx/cards')
    for (const entry of cards) {
      for (const it of entry.items) {
        if (tempByItem[it.id] === undefined) tempByItem[it.id] = 120
        if (minByItem[it.id] === undefined) minByItem[it.id] = 12
      }
    }
  }

  function addDraftRow() {
    draftItems = [...draftItems, { herb: '', grams: 100 }]
  }
  function removeDraftRow(i) {
    draftItems = draftItems.filter((_, idx) => idx !== i)
  }

  async function createCard() {
    notice = ''
    const items = draftItems
      .map((d) => ({ herb: d.herb.trim(), target_grams: Number(d.grams) }))
      .filter((d) => d.herb)
    if (!title.trim() || items.length === 0) {
      notice = '请填写处方名与至少一味饮片'
      return
    }
    busy = true
    try {
      await api('/api/rx/cards', {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), items }),
      })
      title = ''
      draftItems = [{ herb: '甘草', grams: 100 }]
      await load()
    } catch (err) {
      notice = err.message
    } finally {
      busy = false
    }
  }

  async function writeOnce(cardId, itemId) {
    notice = ''
    busy = true
    try {
      await api(`/api/rx/cards/${cardId}/writes`, {
        method: 'POST',
        body: JSON.stringify({
          item_id: itemId,
          steps: [{ name: '清炒', temp_c: Number(tempByItem[itemId]), minutes: Number(minByItem[itemId]) }],
        }),
      })
      await load()
    } catch (err) {
      notice = err.message
    } finally {
      busy = false
    }
  }

  async function issue(cardId) {
    notice = ''
    busy = true
    try {
      const snap = await api(`/api/rx/cards/${cardId}/snapshots`, { method: 'POST' })
      await load()
      notice = `已签发快照 #${snap.snapshot.seq}`
    } catch (err) {
      notice = err.message
    } finally {
      busy = false
    }
  }

  load()
</script>

<section class="page">
  <h2>处方投料汇总</h2>

  {#if role === 'writer'}
    <div class="panel">
      <h3>建卡区</h3>
      <input class="title-input" bind:value={title} placeholder="处方名，如：四君子汤" />
      <table>
        <thead><tr><th>饮片</th><th>目标克重(g)</th><th></th></tr></thead>
        <tbody>
          {#each draftItems as d, i (i)}
            <tr>
              <td><input bind:value={d.herb} placeholder="如：甘草" /></td>
              <td><input type="number" bind:value={d.grams} min="1" /></td>
              <td>
                {#if draftItems.length > 1}
                  <button class="mini" on:click={() => removeDraftRow(i)}>移除</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      <div class="row">
        <button class="ghost" on:click={addDraftRow}>+ 加一味</button>
        <button on:click={createCard} disabled={busy}>建立处方卡</button>
      </div>
    </div>
  {/if}

  {#if notice}<p class="notice">{notice}</p>{/if}

  <h3>现场汇总</h3>
  {#if cards.length === 0}
    <p class="hint">还没有处方卡。{role === 'writer' ? '在上方建卡区建立第一张。' : ''}</p>
  {/if}

  {#each cards as entry (entry.card.id)}
    <div class="panel card">
      <div class="card-head">
        <div>
          <span class="card-title">{entry.card.title}</span>
          <span class="meta">建卡人 {entry.card.created_by} · {fmtTime(entry.card.created_at)}</span>
        </div>
        {#if role === 'writer'}
          <button on:click={() => issue(entry.card.id)} disabled={busy}>签发处方快照</button>
        {/if}
      </div>

      <table>
        <thead>
          <tr>
            <th>饮片</th><th>目标克重</th><th>已成功写入次数</th><th>其中放行</th><th>最近结论</th><th>最近时间</th>
            {#if role === 'writer'}<th>现场写一笔</th>{/if}
          </tr>
        </thead>
        <tbody>
          {#each entry.items as it (it.id)}
            <tr>
              <td>{it.herb}</td>
              <td>{Number(it.target_grams)} g</td>
              <td class="num">{it.write_count}</td>
              <td class="num">{it.pass_count}</td>
              <td>
                {#if it.latest_verdict}
                  <span class="verdict" data-verdict={it.latest_verdict}>{it.latest_verdict}</span>
                  <span class="meta">{it.latest_reason}</span>
                {:else}
                  <span class="meta">暂无写入</span>
                {/if}
              </td>
              <td class="meta">{fmtTime(it.latest_at)}</td>
              {#if role === 'writer'}
                <td>
                  <div class="write-cell">
                    <input type="number" bind:value={tempByItem[it.id]} title="温度℃" />
                    <input type="number" bind:value={minByItem[it.id]} title="时长(分)" />
                    <button class="mini" on:click={() => writeOnce(entry.card.id, it.id)} disabled={busy}>写一笔</button>
                  </div>
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>

      <div class="snaps">
        <span class="meta">已签发快照：</span>
        {#if entry.snapshots.length === 0}<span class="meta">无</span>{/if}
        {#each entry.snapshots as s (s.id)}
          <a href={`#/rx/snap/${s.id}`}>#{s.seq} 快照</a>
        {/each}
      </div>
    </div>
  {/each}
</section>

<style>
  .page { max-width: 1000px; }
  .hint, .meta { color: #6b5b4a; font-size: 13px; }
  .notice { color: #1c7a37; }
  .panel {
    background: #fffaf3; border: 1px solid #e8d9c4; border-radius: 10px;
    padding: 14px 16px; margin: 12px 0 20px;
  }
  h3 { margin: 18px 0 8px; }
  .title-input { width: 280px; margin-bottom: 10px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #f0e6d8; vertical-align: middle; }
  th { color: #7c5a34; font-weight: 600; font-size: 13px; }
  td.num, .num { text-align: center; font-variant-numeric: tabular-nums; }
  .row { display: flex; gap: 10px; margin-top: 10px; }
  .card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .card-title { font-size: 17px; font-weight: 700; color: #5b2a0e; margin-right: 12px; }
  .write-cell { display: flex; gap: 6px; align-items: center; }
  .write-cell input { width: 78px; }
  .mini { padding: 3px 10px; font-size: 13px; }
  .ghost { background: transparent; border: 1px solid #c9b193; color: #7c5a34; }
  .verdict {
    display: inline-block; min-width: 52px; text-align: center;
    padding: 1px 8px; border-radius: 10px; font-size: 13px; margin-right: 6px;
  }
  [data-verdict='放行'] { background: #e4f6e8; color: #1c7a37; }
  [data-verdict='未放行'] { background: #fdeaea; color: #b42318; }
  .snaps { margin-top: 10px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  input { padding: 5px 8px; }
</style>
