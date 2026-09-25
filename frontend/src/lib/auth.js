import { writable } from 'svelte/store'

export const token = writable(localStorage.getItem('herb_token') || '')
export const role = writable(localStorage.getItem('herb_role') || '')
export const username = writable(localStorage.getItem('herb_username') || '')
