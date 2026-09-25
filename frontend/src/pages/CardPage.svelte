<script>
  import { onMount } from 'svelte'
  import { role } from '../lib/auth'
  import { api, fmtTime } from '../lib/api'

  let { cardId, onopensnapshot, onback } = $props()

  let card = $state(null)
  let loadError = $state('')

  // 卡内写入表单
  let pickHerb = $state('')
  let tempC = $state(110)
  let minutes = $state(10)
  let writeError = $state('')
  let writing = $state(false)

  let issuing = $state(false)
  let issueError = $state('')

  async function load() {
    loadError = ''
    try {
      card = await api(`/api/cards/${cardId}`)
      if (!pickHerb && card.herbs.length) pickHerb = card.herbs[0].herb
    } catch (err) {
      loadError = err.message
    }
  }

  async function writeEntry() {
    writeError = ''
    writing = true
    try {
      await api(`/api/cards/${cardId}/entries`, {
        method: 'POST',
        body: JSON.stringify({
          herb: pickHerb,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
        }),
      })
      await load()
    } catch (err) {
      writeError = err.message
    } finally {
      writing = false
    }
  }

  async function issue() {
    issueError = ''
    issuing = true
    try {
      const res = await api(`/api/cards/${cardId}/snapshots`, { method: 'POST' })
      await load()
      onopensnapshot?.(res.id)
    } catch (err) {
      issueError = err.message
    } finally {
      issuing = false
    }
  }

  onMount(load)
</script>

{#if loadError}
  <p class="error">{loadError}</p>
{:else if card}
  <p>
    <button class="ghost" onclick={() => onback?.()}>← 处方汇总链</button>
  </p>

  <section class="card-box">
    <h2>处方卡 #{card.id} · {card.name}</h2>
    <p class="muted">建卡人 {card.created_by} · {fmtTime(card.created_at)}</p>

    <h3>现场汇总（各味已成功写入次数与最近结论）</h3>
    <table>
      <thead>
        <tr>
          <th>饮片</th><th>目标克重(g)</th><th>已成功写入次数</th><th>结论集合</th><th>最近结论</th>
        </tr>
      </thead>
      <tbody>
        {#each card.herbs as h (h.herb)}
          <tr>
            <td>{h.herb}</td>
            <td>{h.target_g}</td>
            <td><strong>{h.count}</strong></td>
            <td>
              {#if h.verdicts.length === 0}
                <span class="muted">暂无</span>
              {:else}
                {#each h.verdicts as v, i}
                  <span class="tag" class:ok={v === '放行'} class:no={v !== '放行'}>{v}</span>{i < h.verdicts.length - 1 ? ' ' : ''}
                {/each}
              {/if}
            </td>
            <td>
              {#if h.latest}
                <span class="tag" class:ok={h.latest.verdict === '放行'} class:no={h.latest.verdict !== '放行'}>{h.latest.verdict}</span>
                <span class="muted">{h.latest.reason} · {fmtTime(h.latest.created_at)}</span>
              {:else}
                <span class="muted">未写入</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>

  {#if $role === 'writer'}
    <section class="card-box">
      <h3>写一笔（挂到本卡）</h3>
      <select bind:value={pickHerb}>
        {#each card.herbs as h (h.herb)}
          <option value={h.herb}>{h.herb}</option>
        {/each}
      </select>
      <input type="number" bind:value={tempC} title="温度℃" placeholder="温度℃" />
      <input type="number" bind:value={minutes} title="时长(分)" placeholder="时长(分)" />
      <button onclick={writeEntry} disabled={writing}>写入清炒记录</button>
      {#if writeError}<p class="error">{writeError}</p>{/if}

      <h3>签发处方快照</h3>
      <p class="muted">签发将冻结此刻各味次数与结论集合；之后新写只改现场卡，快照不动。</p>
      <button onclick={issue} disabled={issuing}>签发快照</button>
      {#if issueError}<p class="error">{issueError}</p>{/if}
    </section>
  {:else}
    <section class="card-box">
      <p class="muted">质检员只读：可查看现场卡与已签发快照，不能写入、不能签发。</p>
    </section>
  {/if}

  <section class="card-box">
    <h3>已签发快照（冻结，不随后续写入变化）</h3>
    {#if card.snapshots.length === 0}
      <p class="muted">尚未签发。</p>
    {:else}
      <table>
        <thead><tr><th>快照</th><th>签发人</th><th>签发时间</th><th></th></tr></thead>
        <tbody>
          {#each card.snapshots as s (s.id)}
            <tr>
              <td>快照 #{s.id}</td>
              <td>{s.created_by}</td>
              <td>{fmtTime(s.created_at)}</td>
              <td><button class="ghost" onclick={() => onopensnapshot?.(s.id)}>打开快照</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{/if}
