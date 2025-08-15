import React, { useState } from 'react'
import { QrCode, Shield, Key, CheckCircle } from 'lucide-react'
import axios from 'axios'
import toast from 'react-hot-toast'

interface MfaSetupProps {
  onComplete?: () => void
  onCancel?: () => void
}

export default function MfaSetup({ onComplete, onCancel }: MfaSetupProps) {
  const [step, setStep] = useState<'setup' | 'verify'>('setup')
  const [qrCode, setQrCode] = useState<string>('')
  const [secret, setSecret] = useState<string>('')
  const [verificationCode, setVerificationCode] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSetupMfa = async () => {
    setIsLoading(true)
    try {
      const response = await axios.post('/api/auth/mfa/setup')
      setQrCode(response.data.qr_code)
      setSecret(response.data.secret)
      setStep('verify')
      toast.success('MFA setup initiated. Scan the QR code with your authenticator app.')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to setup MFA')
    } finally {
      setIsLoading(false)
    }
  }

  const handleVerifyAndEnable = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      toast.error('Please enter a valid 6-digit code')
      return
    }

    setIsLoading(true)
    try {
      await axios.post('/api/auth/mfa/enable', {
        code: verificationCode
      })
      toast.success('MFA enabled successfully!')
      onComplete?.()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Invalid verification code')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto bg-white rounded-2xl shadow-xl p-8">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl mb-4">
          <Shield className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Setup Two-Factor Authentication
        </h2>
        <p className="text-gray-600">
          Add an extra layer of security to your account
        </p>
      </div>

      {step === 'setup' && (
        <div className="space-y-6">
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div className="flex items-start">
              <Shield className="w-5 h-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
              <div>
                <h3 className="font-semibold text-blue-900 mb-1">Why enable MFA?</h3>
                <p className="text-sm text-blue-700">
                  Two-factor authentication adds an extra layer of security by requiring
                  a code from your phone in addition to your password.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">Before you start:</h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li className="flex items-center">
                <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                Install an authenticator app (Google Authenticator, Authy, etc.)
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                Have your phone ready to scan the QR code
              </li>
            </ul>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={handleSetupMfa}
              disabled={isLoading}
              className="flex-1 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 disabled:opacity-50"
            >
              {isLoading ? 'Setting up...' : 'Setup MFA'}
            </button>
            {onCancel && (
              <button
                onClick={onCancel}
                className="px-4 py-3 text-gray-600 hover:text-gray-800 font-medium transition-colors duration-200"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}

      {step === 'verify' && (
        <div className="space-y-6">
          <div className="text-center">
            <div className="bg-gray-50 rounded-xl p-6 mb-6">
              {qrCode && (
                <img
                  src={qrCode}
                  alt="MFA QR Code"
                  className="mx-auto mb-4 rounded-lg"
                />
              )}
              <div className="flex items-center justify-center text-sm text-gray-600 mb-2">
                <QrCode className="w-4 h-4 mr-2" />
                Scan this QR code with your authenticator app
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-4 mb-6">
              <div className="flex items-center justify-center text-sm text-gray-600 mb-2">
                <Key className="w-4 h-4 mr-2" />
                Or enter this key manually:
              </div>
              <code className="text-sm font-mono bg-white px-3 py-2 rounded border break-all">
                {secret}
              </code>
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-3">
              Verification Code
            </label>
            <input
              type="text"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="Enter 6-digit code"
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-center text-lg font-mono focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500"
              maxLength={6}
            />
            <p className="mt-2 text-sm text-gray-500 text-center">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={handleVerifyAndEnable}
              disabled={isLoading || verificationCode.length !== 6}
              className="flex-1 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 disabled:opacity-50"
            >
              {isLoading ? 'Verifying...' : 'Enable MFA'}
            </button>
            <button
              onClick={() => setStep('setup')}
              className="px-4 py-3 text-gray-600 hover:text-gray-800 font-medium transition-colors duration-200"
            >
              Back
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
