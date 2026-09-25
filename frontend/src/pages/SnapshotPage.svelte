<script>
  import { onMount } from 'svelte'
  import { api, fmtTime } from '../lib/api'

  let { cardId, snapshotId, onback } = $props()

  let snap = $state(null)
  let loadError = $state('')

  onMount(async () => {
    try {
      snap = await api(`/api/snapshots/${snapshotId}`)
    } catch (err) {
      loadError = err.message
    }
  })
</script>

{#if loadError}
  <p class="error">{loadError}</p>
{:else if snap}
  <p>
    <button class="ghost" onclick={() => onback?.()}>← 返回现场卡 #{cardId}</button>
  </p>

  <section class="card-box snapshot-banner">
    <h2>❄ 已签发快照 #{snap.id} · {snap.freeze.card_name}</h2>
    <p class="muted">
      签发人 {snap.created_by} · 签发时间 {fmtTime(snap.created_at)}
      {#if snap.freeze.frozen_at}· 冻结时点 {fmtTime(snap.freeze.frozen_at)}{/if}
    </p>
    <p class="muted">这是冻结数据。现场卡此后继续写入不会改变本快照。</p>

    <table>
      <thead>
        <tr>
          <th>饮片</th><th>目标克重(g)</th><th>已成功写入次数（冻结）</th><th>结论集合（冻结）</th><th>最近结论（冻结）</th>
        </tr>
      </thead>
      <tbody>
        {#each snap.freeze.herbs as h (h.herb)}
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
{/if}

<style>
  .snapshot-banner { border-color: #1d4ed8; box-shadow: inset 0 3px 0 #1d4ed8; }
  .snapshot-banner h2 { color: #1d4ed8; margin-top: 4px; }
</style>
