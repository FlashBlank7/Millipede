"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useAuthStore } from "@/store/auth"

export default function EngineerLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (!token) router.replace("/login")
  }, [token, router])

  if (!token) return null

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center gap-6">
        <span className="font-semibold text-gray-900">Millipede · Engineer</span>
        <Link href="/engineer/reviews" className="text-sm text-gray-600 hover:text-gray-900">
          Reviews
        </Link>
      </nav>
      <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
    </div>
  )
}
