import { create } from "zustand"
import { persist } from "zustand/middleware"

interface User {
  id: string
  email: string
  display_name: string
  role: string
  org_id: string
}

interface AuthState {
  user: User | null
  accessToken: string | null
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem("access_token", accessToken)
        localStorage.setItem("refresh_token", refreshToken)
        set({ user, accessToken })
      },
      clearAuth: () => {
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        set({ user: null, accessToken: null })
      },
    }),
    { name: "millipede-auth", partialize: (s) => ({ user: s.user, accessToken: s.accessToken }) }
  )
)
