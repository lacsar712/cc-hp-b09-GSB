<script>
  import { api, fmtTime } from '../lib/api.js'

  let { snapshotId } = $props()
  let data = $state(null)
  let error = $state('')

  api(`/api/rx/snapshots/${snapshotId}`)
    .then((d) => (data = d))
    .catch((e) => (error = e.message))
</script>

<section class="page">
  <p><a href="#/rx">← 返回处方汇总</a></p>

  {#if error}
    <p class="error">{error}</p>
  {:else if !data}
    <p class="hint">载入中…</p>
  {:else}
    {@const s = data.snapshot}
    <div class="frozen-banner">已冻结快照 · 后续写入不改变本页</div>
    <h2>{s.title} <span class="seq">快照 #{s.seq}</span></h2>
    <p class="meta">签发人 {s.issued_by} · 签发时间 {fmtTime(s.issued_at)}</p>

    <table>
      <thead>
        <tr><th>饮片</th><th>目标克重</th><th>签发时已写入次数</th><th>其中放行</th><th>最近结论</th><th>最近时间</th></tr>
      </thead>
      <tbody>
        {#each data.items as it, i (i)}
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
                <span class="meta">签发时暂无写入</span>
              {/if}
            </td>
            <td class="meta">{fmtTime(it.latest_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<style>
  .page { max-width: 1000px; }
  .meta, .hint { color: #6b5b4a; font-size: 13px; }
  .error { color: #b42318; }
  .seq { color: #7c5a34; font-size: 16px; }
  .frozen-banner {
    display: inline-block; background: #eef3ff; color: #2b4aa3;
    border: 1px solid #cdd9f7; border-radius: 999px; padding: 3px 14px; font-size: 13px;
  }
  table { border-collapse: collapse; width: 100%; margin-top: 12px; }
  th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #f0e6d8; }
  th { color: #7c5a34; font-weight: 600; font-size: 13px; }
  td.num { text-align: center; font-variant-numeric: tabular-nums; }
  .verdict {
    display: inline-block; min-width: 52px; text-align: center;
    padding: 1px 8px; border-radius: 10px; font-size: 13px; margin-right: 6px;
  }
  [data-verdict='放行'] { background: #e4f6e8; color: #1c7a37; }
  [data-verdict='未放行'] { background: #fdeaea; color: #b42318; }
</style>
