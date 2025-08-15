import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import axios from 'axios'
import toast from 'react-hot-toast'

export interface User {
  id: number
  email: string
  full_name?: string
  role: string
  is_active: boolean
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string, mfaCode?: string) => Promise<boolean | { mfa_required: boolean }>
  register: (email: string, fullName: string, password: string) => Promise<boolean>
  logout: () => void
  setUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (email: string, password: string, mfaCode?: string) => {
        try {
          if (!mfaCode) {
            // First step: check if MFA is required
            const response = await axios.post('/auth/login', {
              email,
              password,
            })

            if (response.data.mfa_required) {
              return { mfa_required: true } // Need MFA code
            }

            // MFA not required, we got the token directly
            if (response.data.access_token) {
              const { access_token } = response.data

              // Set axios default header
              axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

              // Get user info (would need to add endpoint)
              const user: User = {
                id: 1, // TODO: Get from token or separate endpoint
                email,
                role: 'admin', // TODO: Get from token
                is_active: true,
              }

              set({
                user,
                token: access_token,
                isAuthenticated: true,
              })

              toast.success('Successfully logged in!')
              return true
            }
          } else {
            // Second step: verify MFA and get token
            const response = await axios.post('/auth/mfa/verify', {
              email,
              code: mfaCode,
            })

            const { access_token } = response.data

            // Set axios default header
            axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

            // Get user info (would need to add endpoint)
            const user: User = {
              id: 1, // TODO: Get from token or separate endpoint
              email,
              role: 'admin', // TODO: Get from token
              is_active: true,
            }

            set({
              user,
              token: access_token,
              isAuthenticated: true,
            })

            toast.success('Successfully logged in!')
            return true
          }
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Login failed'
          toast.error(message)
          return false
        }

        return false
      },

      register: async (email: string, fullName: string, password: string) => {
        try {
          await axios.post('/auth/register', {
            email,
            full_name: fullName,
            password,
          })

          toast.success('Registration submitted! Please wait for admin approval.')
          return true
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Registration failed'
          toast.error(message)
          return false
        }
      },

      logout: () => {
        delete axios.defaults.headers.common['Authorization']
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        })
        toast.success('Logged out successfully')
      },

      setUser: (user: User) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          axios.defaults.headers.common['Authorization'] = `Bearer ${state.token}`
        }
      },
    }
  )
)
