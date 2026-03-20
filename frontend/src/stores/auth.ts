import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/index'

interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  async function login(username: string, password: string) {
    const data: any = await api.post('/auth/login', { username, password })
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
  }

  async function register(username: string, email: string, password: string) {
    await api.post('/auth/register', { username, email, password })
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { user, token, login, register, logout }
})