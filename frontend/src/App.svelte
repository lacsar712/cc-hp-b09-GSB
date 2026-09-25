<script>
  import { onMount } from 'svelte'
  import { token, role, username } from './lib/auth'
  import { api, saveSession, clearSession } from './lib/api'
  import HomePage from './pages/HomePage.svelte'
  import RxLanding from './pages/RxLanding.svelte'
  import CardPage from './pages/CardPage.svelte'
  import SnapshotPage from './pages/SnapshotPage.svelte'

  let loginName = 'processor'
  let loginPwd = 'herb123456'
  let loginError = ''
  let route = { name: 'home' }

  function parseHash() {
    const hash = location.hash.replace(/^#/, '') || '/'
    const parts = hash.split('/').filter(Boolean)
    if (parts.length === 0) return { name: 'home' }
    if (parts[0] === 'rx') {
      if (parts.length === 1) return { name: 'rx' }
      if (parts.length >= 4 && parts[2] === 'snapshots') {
        return { name: 'snapshot', cardId: Number(parts[1]), snapshotId: Number(parts[3]) }
      }
      return { name: 'card', cardId: Number(parts[1]) }
    }
    return { name: 'home' }
  }

  function syncRoute() {
    route = parseHash()
  }

  onMount(() => {
    syncRoute()
    window.addEventListener('hashchange', syncRoute)
  })

  async function enter() {
    loginError = ''
    try {
      saveSession(await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: loginName, password: loginPwd }),
      }))
    } catch (err) {
      loginError = err.message
    }
  }

  function leave() {
    clearSession()
    location.hash = ''
  }

  function go(hash) {
    location.hash = hash
  }
</script>

{#if !$token}
  <main class="narrow">
    <h1>饮片炮制记录台</h1>
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>
    <input bind:value={loginName} placeholder="用户名" />
    <input type="password" bind:value={loginPwd} placeholder="密码" />
    <button onclick={enter}>登录</button>
    {#if loginError}<p class="error">{loginError}</p>{/if}
    <p class="hint">processor / herb123456 可写；checker / check123456 只读</p>
  </main>
{:else}
  <header class="topbar">
    <div class="brand">饮片炮制记录台</div>
    <nav>
      <a href="#/" class:active={route.name === 'home'}>记录台</a>
      <a href="#/rx" class:active={route.name === 'rx' || route.name === 'card' || route.name === 'snapshot'}>处方汇总链</a>
    </nav>
    <div class="who">
      <span>{$username}（{$role === 'writer' ? '炮制员·可写' : '质检员·只读'}）</span>
      <button onclick={leave}>退出</button>
    </div>
  </header>

  <main class="narrow">
    {#if route.name === 'home'}
      <HomePage />
    {:else if route.name === 'rx'}
      <RxLanding
        onopen={(id) => go(`#/rx/${id}`)}
        onopensnapshot={(p) => go(`#/rx/${p.cardId}/snapshots/${p.snapshotId}`)}
      />
    {:else if route.name === 'card'}
      <CardPage
        cardId={route.cardId}
        onopensnapshot={(sid) => go(`#/rx/${route.cardId}/snapshots/${sid}`)}
        onback={() => go('#/rx')}
      />
    {:else if route.name === 'snapshot'}
      <SnapshotPage
        cardId={route.cardId}
        snapshotId={route.snapshotId}
        onback={() => go(`#/rx/${route.cardId}`)}
      />
    {/if}
  </main>
{/if}

<style>
  :global(body) {
    margin: 0;
    background: #faf6f0;
    color: #3f2f1f;
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  }
  main.narrow {
    max-width: 860px;
    margin: 24px auto;
    padding: 0 16px 48px;
  }
  h1 { color: #7c2d12; }
  input, select {
    margin: 0 8px 8px 0;
    padding: 6px 8px;
    border: 1px solid #c9b8a4;
    border-radius: 4px;
  }
  button {
    padding: 6px 14px;
    border: 1px solid #7c2d12;
    border-radius: 4px;
    background: #7c2d12;
    color: #fff;
    cursor: pointer;
  }
  button.ghost { background: #fff; color: #7c2d12; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .error { color: #b91c1c; }
  .hint { color: #8a7a6a; font-size: 13px; }
  .topbar {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 10px 20px;
    background: #7c2d12;
    color: #fdf3e7;
  }
  .topbar .brand { font-weight: 700; font-size: 16px; }
  .topbar nav { display: flex; gap: 14px; flex: 1; }
  .topbar a { color: #f6ddc4; text-decoration: none; padding: 4px 8px; border-radius: 4px; }
  .topbar a.active { background: rgba(255, 255, 255, .18); color: #fff; }
  .topbar .who { display: flex; align-items: center; gap: 10px; font-size: 13px; }
  .topbar .who button { background: #fdf3e7; color: #7c2d12; border: none; padding: 4px 10px; }
  .card-box {
    background: #fff;
    border: 1px solid #e4d7c7;
    border-radius: 8px;
    padding: 16px 18px;
    margin: 14px 0;
  }
  .muted { color: #8a7a6a; }
  table { border-collapse: collapse; width: 100%; background: #fff; }
  th, td { border: 1px solid #e4d7c7; padding: 8px 10px; text-align: left; }
  th { background: #f3e8db; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
  .tag.ok { background: #dcfce7; color: #166534; }
  .tag.no { background: #fee2e2; color: #991b1b; }
</style>
