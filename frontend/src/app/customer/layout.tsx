"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useAuthStore } from "@/store/auth"
import { useEffect } from "react"

const NAV = [
  { href: "/customer", label: "Projects" },
  { href: "/customer/new", label: "New Project" },
  { href: "/customer/deliveries", label: "Deliveries" },
]

export default function CustomerLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { user, clearAuth } = useAuthStore()

  useEffect(() => {
    if (!user) router.replace("/login")
  }, [user, router])

  if (!user) return null

  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-14 border-b border-gray-200 bg-white flex items-center px-6 justify-between shrink-0">
        <div className="flex items-center gap-6">
          <span className="font-semibold text-gray-900">Millipede</span>
          <nav className="flex items-center gap-1">
            {NAV.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  pathname === href
                    ? "bg-gray-100 text-gray-900 font-medium"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user.display_name}</span>
          <button
            onClick={() => { clearAuth(); router.push("/login") }}
            className="text-sm text-gray-500 hover:text-gray-900"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  )
}
