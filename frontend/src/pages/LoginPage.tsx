import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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

const registerSchema = z.object({
  fullName: z.string().min(1, 'Full name is required'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

type LoginForm = z.infer<typeof loginSchema>
type RegisterForm = z.infer<typeof registerSchema>

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [needsMfa, setNeedsMfa] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [showRegister, setShowRegister] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const { login, register } = useAuthStore()
  const navigate = useNavigate()

  // Reset MFA state when component mounts
  useEffect(() => {
    setNeedsMfa(false)
  }, [])

  const {
    register: loginRegister,
    handleSubmit,
    formState: { errors },
    getValues,
    watch,
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const {
    register: registerRegister,
    handleSubmit: handleRegisterSubmit,
    formState: { errors: registerErrors },
    reset: resetRegisterForm,
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  })

  // Watch email field to reset MFA state when user changes email
  const watchedEmail = watch('email')
  useEffect(() => {
    setNeedsMfa(false)
  }, [watchedEmail])

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true)
    try {
      const result = await login(data.email, data.password, data.mfaCode)

      // If login returns an object with mfa_required, handle MFA flow
      if (typeof result === 'object' && result.mfa_required) {
        setNeedsMfa(true)
      } else if (result === true) {
        // Successful login
        setNeedsMfa(false)
        // Explicitly navigate to dashboard after successful auth
        navigate('/dashboard', { replace: true })
      }
      // If result is false, login failed (error will be shown by auth store)
    } finally {
      setIsLoading(false)
    }
  }

  const onRegisterSubmit = async (data: RegisterForm) => {
    setIsRegistering(true)
    try {
      const success = await register(data.email, data.fullName, data.password)
      if (success) {
        setShowRegister(false)
        resetRegisterForm()
      }
    } finally {
      setIsRegistering(false)
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
                  {...loginRegister('email')}
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
                  {...loginRegister('password')}
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
                  {...loginRegister('mfaCode')}
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
          <p className="text-sm text-gray-400 font-medium mb-4">
            Secure document management for journalists
          </p>
          <div className="flex items-center justify-center space-x-2">
            <span className="text-sm text-gray-500">Don't have an account?</span>
            <button
              onClick={() => setShowRegister(true)}
              className="text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors"
            >
              Request Access
            </button>
          </div>
        </div>

        {/* Registration Modal */}
        {showRegister && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl p-8 w-full max-w-md">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">Request Access</h2>
              <p className="text-gray-600 mb-6">
                Submit your information to request access to the platform. An administrator will review your request.
              </p>
              <form onSubmit={handleRegisterSubmit(onRegisterSubmit)} className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-800 mb-2">
                    Full Name
                  </label>
                  <input
                    {...registerRegister('fullName')}
                    type="text"
                    className={clsx(
                      "w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500",
                      registerErrors.fullName && "border-red-300 focus:border-red-500"
                    )}
                    placeholder="Your full name"
                    disabled={isRegistering}
                  />
                  {registerErrors.fullName && (
                    <p className="mt-1 text-sm text-red-500">{registerErrors.fullName.message}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-800 mb-2">
                    Email Address
                  </label>
                  <input
                    {...registerRegister('email')}
                    type="email"
                    className={clsx(
                      "w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500",
                      registerErrors.email && "border-red-300 focus:border-red-500"
                    )}
                    placeholder="your.email@example.com"
                    disabled={isRegistering}
                  />
                  {registerErrors.email && (
                    <p className="mt-1 text-sm text-red-500">{registerErrors.email.message}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-800 mb-2">
                    Password
                  </label>
                  <input
                    {...registerRegister('password')}
                    type="password"
                    className={clsx(
                      "w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500",
                      registerErrors.password && "border-red-300 focus:border-red-500"
                    )}
                    placeholder="Create a secure password (min 8 characters)"
                    disabled={isRegistering}
                  />
                  {registerErrors.password && (
                    <p className="mt-1 text-sm text-red-500">{registerErrors.password.message}</p>
                  )}
                </div>
                <div className="flex space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowRegister(false)}
                    className="flex-1 px-4 py-3 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl font-semibold transition-colors"
                    disabled={isRegistering}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className={clsx(
                      "flex-1 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-colors",
                      isRegistering && "opacity-50 cursor-not-allowed"
                    )}
                    disabled={isRegistering}
                  >
                    {isRegistering ? 'Submitting...' : 'Submit Request'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
