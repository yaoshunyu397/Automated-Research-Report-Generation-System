import { useCallback, useEffect, useRef, useState } from 'react'
import { submitAuthRequest } from '../api'
import type { AuthUser } from '../types'

export function useAuth(onLoggedOut: () => void) {
  const [authToken, setAuthToken] = useState(() => sessionStorage.getItem('survey2_token') ?? '')
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => {
    const raw = sessionStorage.getItem('survey2_user')
    if (!raw) return null
    try { return JSON.parse(raw) as AuthUser } catch { return null }
  })
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [authUsername, setAuthUsername] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const onLoggedOutRef = useRef(onLoggedOut)

  useEffect(() => {
    onLoggedOutRef.current = onLoggedOut
  }, [onLoggedOut])

  const logout = useCallback(() => {
    sessionStorage.removeItem('survey2_token')
    sessionStorage.removeItem('survey2_user')
    setAuthToken('')
    setAuthUser(null)
    onLoggedOutRef.current()
  }, [])

  const apiFetch = useCallback(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const headers = new Headers(init.headers)
    if (authToken) headers.set('Authorization', `Bearer ${authToken}`)
    const response = await fetch(input, { ...init, headers })
    if (response.status === 401) {
      logout()
      throw new Error('登录已失效，请重新登录')
    }
    return response
  }, [authToken, logout])

  const submitAuth = useCallback(async () => {
    setAuthLoading(true)
    setAuthError(null)
    try {
      const data = await submitAuthRequest(authMode, authUsername.trim(), authPassword)
      sessionStorage.setItem('survey2_token', data.token)
      sessionStorage.setItem('survey2_user', JSON.stringify(data.user))
      setAuthToken(data.token)
      setAuthUser(data.user)
      setAuthPassword('')
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setAuthLoading(false)
    }
  }, [authMode, authPassword, authUsername])

  const changeAuthMode = useCallback((mode: 'login' | 'register') => {
    setAuthMode(mode)
    setAuthError(null)
  }, [])

  return {
    authToken,
    authUser,
    authMode,
    authUsername,
    authPassword,
    authLoading,
    authError,
    setAuthUsername,
    setAuthPassword,
    setAuthError,
    changeAuthMode,
    submitAuth,
    logout,
    apiFetch,
  }
}
