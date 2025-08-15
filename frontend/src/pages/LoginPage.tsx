import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Lock, Mail, Shield } from 'lucide-react'
import { useAuthStore } from '../services/auth'
import { clsx } from 'clsx'

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
  mfaCode: z.string().optional(),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [needsMfa, setNeedsMfa] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuthStore()

  // Reset MFA state when component mounts
  useEffect(() => {
    setNeedsMfa(false)
  }, [])

  const {
    register,
    handleSubmit,
    formState: { errors },
    getValues,
    watch,
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  // Watch email field to reset MFA state when user changes email
  const watchedEmail = watch('email')
  useEffect(() => {
    setNeedsMfa(false)
  }, [watchedEmail])

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true)
    try {
      const success = await login(data.email, data.password, data.mfaCode)

      if (!success && !data.mfaCode) {
        setNeedsMfa(true)
      } else if (success) {
        // Reset MFA state on successful login
        setNeedsMfa(false)
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="apple-inspired-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-600 rounded-3xl mb-6 shadow-lg shadow-blue-500/25">
            <Shield className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold apple-gradient-text mb-3">
            Welcome Back
          </h1>
          <p className="text-gray-500 text-lg">
            Sign in to access your documents
          </p>
        </div>

        <div className="apple-card">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-semibold text-gray-800 mb-3">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  {...register('email')}
                  type="email"
                  className={clsx(
                    'w-full pl-12 pr-4 py-4 bg-gray-50/50 border border-gray-200 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200',
                    errors.email && 'border-red-300 focus:border-red-500 focus:ring-red-500/20'
                  )}
                  placeholder="test@example.com"
                  disabled={isLoading}
                />
              </div>
              {errors.email && (
                <p className="mt-2 text-sm text-red-500 font-medium">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-semibold text-gray-800 mb-3">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  {...register('password')}
                  type={showPassword ? 'text' : 'password'}
                  className={clsx(
                    'w-full pl-12 pr-12 py-4 bg-gray-50/50 border border-gray-200 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200',
                    errors.password && 'border-red-300 focus:border-red-500 focus:ring-red-500/20'
                  )}
                  placeholder="••••••••••••"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors duration-200"
                  disabled={isLoading}
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-2 text-sm text-red-500 font-medium">{errors.password.message}</p>
              )}
            </div>

            {/* MFA Code */}
            {needsMfa && (
              <div className="animate-slide-up">
                <label htmlFor="mfaCode" className="block text-sm font-semibold text-gray-800 mb-3">
                  Two-Factor Authentication Code
                </label>
                <div className="relative">
                  <Shield className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <input
                    {...register('mfaCode')}
                    type="text"
                    className={clsx(
                      'w-full pl-12 pr-4 py-4 bg-gray-50/50 border border-gray-200 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200',
                      errors.mfaCode && 'border-red-300 focus:border-red-500 focus:ring-red-500/20'
                    )}
                    placeholder="Enter 6-digit code"
                    maxLength={6}
                    disabled={isLoading}
                  />
                </div>
                {errors.mfaCode && (
                  <p className="mt-2 text-sm text-red-500 font-medium">{errors.mfaCode.message}</p>
                )}
                <p className="mt-2 text-sm text-gray-500">
                  Enter the 6-digit code from your authenticator app
                </p>
              </div>
            )}

            {            /* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className={clsx(
                'apple-button w-full',
                isLoading && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-3" />
                  Signing in...
                </div>
              ) : needsMfa ? (
                'Verify & Sign In'
              ) : (
                'Sign In'
              )}
            </button>
          </form>
        </div>

        <div className="text-center mt-8">
          <p className="text-sm text-gray-400 font-medium">
            Secure document management for journalists
          </p>
        </div>
      </div>
    </div>
  )
}
