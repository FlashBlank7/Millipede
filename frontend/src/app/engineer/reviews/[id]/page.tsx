"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { api } from "@/lib/api"

interface StageOutput {
  id: string
  stage_name: string
  output_type: string
  content: Record<string, unknown>
  is_human_modified: boolean
  created_at: string
}

type Action = "accept" | "modify" | "reject"

export default function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const [outputs, setOutputs] = useState<StageOutput[]>([])
  const [runcard, setRuncard] = useState<{ current_state: string } | null>(null)
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState<Action>("accept")
  const [comment, setComment] = useState("")
  const [modifications, setModifications] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [dispatching, setDispatching] = useState(false)
  const [message, setMessage] = useState("")

  useEffect(() => {
    Promise.all([
      api.get(`/engineer/reviews`).then((r) =>
        setRuncard(r.data.find((rc: { id: string; current_state: string }) => rc.id === id) ?? null)
      ),
      api.get(`/engineer/reviews/${id}/outputs`).then((r) => setOutputs(r.data)),
    ]).finally(() => setLoading(false))
  }, [id])

  const isAwaitingReview = runcard?.current_state?.startsWith("AWAIT_REVIEW_")
  const isAwaitingDispatch = runcard?.current_state?.startsWith("AWAIT_DISPATCH_")

  async function submitAction() {
    setSubmitting(true)
    setMessage("")
    try {
      let mods: Record<string, unknown> | null = null
      if (action === "modify" && modifications.trim()) {
        mods = JSON.parse(modifications)
      }
      const res = await api.post(`/engineer/reviews/${id}/action`, {
        action,
        comment: comment || null,
        modifications: mods,
      })
      setMessage(`✓ State → ${res.data.new_state}`)
      // Refresh runcard state
      const rv = await api.get("/engineer/reviews")
      setRuncard(rv.data.find((rc: { id: string; current_state: string }) => rc.id === id) ?? null)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setMessage(`✗ ${err.response?.data?.detail ?? "Error"}`)
    } finally {
      setSubmitting(false)
    }
  }

  async function submitDispatch() {
    setDispatching(true)
    setMessage("")
    try {
      const res = await api.post(`/engineer/reviews/${id}/dispatch`)
      setMessage(`✓ Dispatched → ${res.data.new_state}`)
      setTimeout(() => router.push("/engineer/reviews"), 1500)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setMessage(`✗ ${err.response?.data?.detail ?? "Error"}`)
    } finally {
      setDispatching(false)
    }
  }

  if (loading) return <p className="text-gray-500">Loading…</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Review RunCard</h1>
          <p className="text-xs font-mono text-gray-400 mt-1">{id}</p>
        </div>
        <span className="text-sm bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full">
          {runcard?.current_state ?? "unknown"}
        </span>
      </div>

      {/* Stage outputs */}
      <section>
        <h2 className="text-sm font-semibold text-gray-600 mb-3">Stage Outputs</h2>
        {outputs.length === 0 ? (
          <p className="text-sm text-gray-400">No outputs yet.</p>
        ) : (
          <div className="space-y-3">
            {outputs.map((o) => (
              <div key={o.id} className="bg-white border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{o.stage_name}</span>
                  <span className="text-xs text-gray-400">{o.output_type}</span>
                  {o.is_human_modified && (
                    <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded">
                      modified
                    </span>
                  )}
                </div>
                <pre className="text-xs bg-gray-50 rounded p-3 overflow-auto max-h-64">
                  {JSON.stringify(o.content, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Review action panel */}
      {isAwaitingReview && (
        <section className="bg-white border rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-600">Review Action</h2>
          <div className="flex gap-3">
            {(["accept", "modify", "reject"] as Action[]).map((a) => (
              <button
                key={a}
                onClick={() => setAction(a)}
                className={`px-4 py-1.5 rounded text-sm border transition ${
                  action === a
                    ? a === "reject"
                      ? "bg-red-500 text-white border-red-500"
                      : a === "modify"
                      ? "bg-blue-500 text-white border-blue-500"
                      : "bg-green-500 text-white border-green-500"
                    : "text-gray-600 border-gray-300 hover:border-gray-400"
                }`}
              >
                {a}
              </button>
            ))}
          </div>

          {action === "modify" && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Modifications (JSON object merged into latest output content)
              </label>
              <textarea
                value={modifications}
                onChange={(e) => setModifications(e.target.value)}
                rows={4}
                className="w-full text-xs font-mono border rounded p-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder='{"key": "new_value"}'
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-gray-500 mb-1">Comment (optional)</label>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
              placeholder="Leave a note…"
            />
          </div>

          <button
            onClick={submitAction}
            disabled={submitting}
            className="px-5 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </section>
      )}

      {/* Dispatch panel */}
      {isAwaitingDispatch && (
        <section className="bg-white border rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-600 mb-3">Confirm Dispatch</h2>
          <p className="text-sm text-gray-500 mb-4">
            Review accepted. Confirm to trigger packaging and deliver the analysis pack.
          </p>
          <button
            onClick={submitDispatch}
            disabled={dispatching}
            className="px-5 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
          >
            {dispatching ? "Dispatching…" : "Confirm Dispatch"}
          </button>
        </section>
      )}

      {message && (
        <p className={`text-sm ${message.startsWith("✓") ? "text-green-600" : "text-red-500"}`}>
          {message}
        </p>
      )}
    </div>
  )
}
