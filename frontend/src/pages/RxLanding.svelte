<script>
  import { onMount } from 'svelte'
  import { role } from '../lib/auth'
  import { api, fmtTime } from '../lib/api'

  let { onopen, onopensnapshot } = $props()

  let cards = $state([])
  let snaps = $state([])
  let loadError = $state('')

  // 建卡表单
  let cardName = $state('')
  let herbs = $state([{ herb: '甘草', target_g: 100 }])
  let createError = $state('')
  let creating = $state(false)

  async function load() {
    loadError = ''
    try {
      [cards, snaps] = await Promise.all([api('/api/cards'), api('/api/snapshots')])
    } catch (err) {
      loadError = err.message
    }
  }

  function addHerbRow() {
    herbs = [...herbs, { herb: '', target_g: 0 }]
  }

  function removeHerbRow(i) {
    herbs = herbs.filter((_, idx) => idx !== i)
  }

  async function createCard() {
    createError = ''
    const payload = {
      name: cardName.trim(),
      herbs: herbs
        .filter((h) => h.herb.trim())
        .map((h) => ({ herb: h.herb.trim(), target_g: Number(h.target_g) })),
    }
    if (!payload.name) {
      createError = '请填写处方卡名称'
      return
    }
    if (payload.herbs.length === 0) {
      createError = '至少挂一味饮片'
      return
    }
    if (payload.herbs.some((h) => !(h.target_g > 0))) {
      createError = '目标克重必须大于 0'
      return
    }
    creating = true
    try {
      const res = await api('/api/cards', { method: 'POST', body: JSON.stringify(payload) })
      cardName = ''
      herbs = [{ herb: '甘草', target_g: 100 }]
      await load()
      location.hash = `#/rx/${res.id}`
    } catch (err) {
      createError = err.message
    } finally {
      creating = false
    }
  }

  onMount(load)
</script>

<h1>处方投料汇总链</h1>

{#if $role === 'writer'}
  <section class="card-box">
    <h2>建卡区</h2>
    <p class="muted">炮制员建立处方卡，挂上多味饮片与各味目标克重。</p>
    <input bind:value={cardName} placeholder="处方卡名称，如 四君子汤" style="min-width: 260px" />
    <table>
      <thead>
        <tr><th>饮片</th><th>目标克重(g)</th><th></th></tr>
      </thead>
      <tbody>
        {#each herbs as h, i (i)}
          <tr>
            <td><input bind:value={h.herb} placeholder="饮片名" /></td>
            <td><input type="number" bind:value={h.target_g} min="0" step="1" /></td>
            <td>
              {#if herbs.length > 1}
                <button class="ghost" onclick={() => removeHerbRow(i)}>移除</button>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    <p>
      <button class="ghost" onclick={addHerbRow}>加一味</button>
      <button onclick={createCard} disabled={creating}>建立处方卡</button>
    </p>
    {#if createError}<p class="error">{createError}</p>{/if}
  </section>
{:else}
  <section class="card-box">
    <h2>建卡区</h2>
    <p class="muted">质检员只读：不能建卡。</p>
  </section>
{/if}

<section class="card-box">
  <h2>现场汇总</h2>
  {#if loadError}<p class="error">{loadError}</p>{/if}
  {#if cards.length === 0}
    <p class="muted">还没有处方卡。</p>
  {:else}
    <table>
      <thead>
        <tr><th>卡</th><th>饮片味数</th><th>已签发快照</th><th>建卡人</th><th></th></tr>
      </thead>
      <tbody>
        {#each cards as c (c.id)}
          <tr>
            <td>#{c.id} {c.name}</td>
            <td>{c.herb_count}</td>
            <td>{c.snapshot_count}{#if c.last_snapshot_at} · 最近 {fmtTime(c.last_snapshot_at)}{/if}</td>
            <td>{c.created_by}</td>
            <td><button class="ghost" onclick={() => onopen?.(c.id)}>打开专页</button></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<section class="card-box">
  <h2>已签发快照</h2>
  {#if snaps.length === 0}
    <p class="muted">还没有签发过快照。</p>
  {:else}
    <table>
      <thead>
        <tr><th>快照</th><th>所属处方卡</th><th>签发人</th><th>签发时间</th><th></th></tr>
      </thead>
      <tbody>
        {#each snaps as s (s.id)}
          <tr>
            <td>快照 #{s.id}</td>
            <td>#{s.card_id} {s.card_name}</td>
            <td>{s.created_by}</td>
            <td>{fmtTime(s.created_at)}</td>
            <td><button class="ghost" onclick={() => onopensnapshot?.({ cardId: s.card_id, snapshotId: s.id })}>查看冻结快照</button></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>
