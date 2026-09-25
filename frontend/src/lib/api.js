import { get } from 'svelte/store'
import { token, role, username } from './auth'

export async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(get(token) ? { Authorization: `Bearer ${get(token)}` } : {}),
      ...(options.headers || {}),
    },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || '请求失败')
  return data
}

export function saveSession(data) {
  token.set(data.access_token)
  role.set(data.role)
  username.set(data.username)
  localStorage.setItem('herb_token', data.access_token)
  localStorage.setItem('herb_role', data.role)
  localStorage.setItem('herb_username', data.username)
}

export function clearSession() {
  token.set('')
  role.set('')
  username.set('')
  localStorage.removeItem('herb_token')
  localStorage.removeItem('herb_role')
  localStorage.removeItem('herb_username')
}

export function fmtTime(s) {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return String(s)
  return d.toLocaleString('zh-CN', { hour12: false })
}
