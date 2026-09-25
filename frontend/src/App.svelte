<script>
  import { api } from './lib/api.js'
  import Home from './pages/Home.svelte'
  import RxPage from './pages/RxPage.svelte'
  import Snapshot from './pages/Snapshot.svelte'

  let username = $state('processor')
  let password = $state('herb123456')
  let token = $state(localStorage.getItem('herb_token') || '')
  let role = $state(localStorage.getItem('herb_role') || '')
  let route = $state(window.location.hash)
  let loginError = $state('')

  window.addEventListener('hashchange', () => (route = window.location.hash))

  // 形如 #/rx/snap/12
  const snapMatch = () => route.match(/^#\/rx\/snap\/(\d+)/)

  async function enter() {
    loginError = ''
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      token = data.access_token
      role = data.role
      localStorage.setItem('herb_token', token)
      localStorage.setItem('herb_role', role)
      if (!window.location.hash) window.location.hash = '#/'
    } catch (err) {
      loginError = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
  }
</script>

{#if !token}
  <main class="narrow">
    <h1>饮片炮制记录台</h1>
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>
    <div class="login">
      <input bind:value={username} placeholder="用户名" />
      <input type="password" bind:value={password} placeholder="密码" />
      <button on:click={enter}>登录</button>
    </div>
    {#if loginError}<p class="error">{loginError}</p>{/if}
    <p class="hint">processor / herb123456 可写；checker / check123456 只读</p>
  </main>
{:else}
  <header class="topbar">
    <span class="brand">饮片炮制记录台</span>
    <nav>
      <a href="#/" class:active={route === '' || route === '#/' || route === '#'}>首页</a>
      <a href="#/rx" class:active={route.startsWith('#/rx')}>处方汇总</a>
    </nav>
    <span class="who">
      {role === 'writer' ? '炮制员' : '质检员'}
      <button class="mini" on:click={leave}>退出</button>
    </span>
  </header>

  <main>
    {#key route}
      {#if snapMatch()}
        <Snapshot snapshotId={Number(snapMatch()[1])} />
      {:else if route.startsWith('#/rx')}
        <RxPage {role} />
      {:else}
        <Home {role} onLogout={leave} />
      {/if}
    {/key}
  </main>
{/if}

<style>
  :global(body) { margin: 0; background: #f7f1e8; color: #3f2f1f; font-family: sans-serif; }
  main { max-width: 1000px; margin: 22px auto; padding: 0 18px; }
  main.narrow { max-width: 560px; }
  h1 { color: #7c2d12; }
  .login { display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0; }
  input { padding: 6px 8px; }
  .hint { color: #6b5b4a; font-size: 13px; }
  .error { color: #b42318; }
  .topbar {
    display: flex; align-items: center; gap: 22px;
    background: #5b2a0e; color: #f7eedd; padding: 10px 20px;
  }
  .brand { font-weight: 700; }
  .topbar nav { display: flex; gap: 16px; flex: 1; }
  .topbar a { color: #e8d3b8; text-decoration: none; padding: 3px 6px; border-radius: 6px; }
  .topbar a.active { background: #7c3a18; color: #fff; }
  .who { font-size: 13px; display: flex; gap: 10px; align-items: center; }
  .mini { padding: 2px 10px; font-size: 12px; }
</style>
