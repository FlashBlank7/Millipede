"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { runcardsApi } from "@/lib/api"
import { RunCardSocket } from "@/lib/ws"
import { use } from "react"

const STATE_LABELS: Record<string, { label: string; phase: number }> = {
  REQ_READY: { label: "需求确认", phase: 0 },
  PRE_ANALYZING: { label: "数据初步扫描", phase: 1 },
  PREPROCESSING: { label: "数据清洗", phase: 2 },
  DA_PLANNING: { label: "分析规划", phase: 3 },
  DATA_ANALYZING: { label: "深度分析", phase: 4 },
  AWAIT_REVIEW_DA_REPORT: { label: "报告审查中", phase: 5 },
  AWAIT_DISPATCH_DA_REPORT: { label: "等待发出", phase: 5 },
  PACKAGING: { label: "打包交付", phase: 6 },
  DELIVERED: { label: "已交付", phase: 7 },
  FAILED: { label: "执行失败", phase: -1 },
}

const TOTAL_PHASES = 8

export default function ProjectProgressPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params)
  const [logs, setLogs] = useState<string[]>([])
  const [liveState, setLiveState] = useState<string | null>(null)
  const [planProgress, setPlanProgress] = useState<{ current: number; total: number } | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const { data: runcards } = useQuery({
    queryKey: ["runcards", projectId],
    queryFn: () => runcardsApi.list(projectId).then((r) => r.data),
    refetchInterval: 10000,
  })

  const mainRuncard = runcards?.find((r: any) => r.kind === "main")

  useEffect(() => {
    if (!mainRuncard) return
    const sock = new RunCardSocket(mainRuncard.id).connect()

    sock.on((event) => {
      const { event_type, payload } = event

      if (event_type === "runcard.state_changed") {
        setLiveState(payload.to as string)
        setLogs((prev) => [...prev, `→ ${payload.to}`])
      }
      if (event_type === "agent.step_started") {
        const p = payload as any
        setPlanProgress((prev) => ({ current: p.step_index, total: prev?.total || mainRuncard.plan_steps?.length || 0 }))
        setLogs((prev) => [...prev, `  [${p.step_index}] ${p.title}`])
      }
      if (event_type === "agent.step_completed") {
        const p = payload as any
        setPlanProgress((prev) => ({ current: p.step_index + 1, total: prev?.total || 0 }))
        setLogs((prev) => [...prev, `  ✓ ${p.summary || p.title}`])
      }
      if (event_type === "agent.step_failed") {
        const p = payload as any
        setLogs((prev) => [...prev, `  ✕ ${p.title}: ${p.error}`])
      }
    })

    return () => sock.disconnect()
  }, [mainRuncard?.id])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  const currentState = liveState || mainRuncard?.current_state || "REQ_READY"
  const stateInfo = STATE_LABELS[currentState] || { label: currentState, phase: 0 }
  const progressPct = stateInfo.phase < 0 ? 0 : Math.round((stateInfo.phase / TOTAL_PHASES) * 100)

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <div className="text-xs text-gray-400 font-mono mb-1">{projectId.slice(0, 8)}</div>
        <h1 className="text-xl font-semibold text-gray-900">项目进度</h1>
      </div>

      {/* Progress bar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-900">{stateInfo.label}</span>
          <span className="text-sm text-gray-400">{progressPct}%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${
              currentState === "FAILED" ? "bg-red-500" :
              currentState === "DELIVERED" ? "bg-green-500" :
              "bg-gray-900 animate-pulse"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {planProgress && (
          <div className="text-xs text-gray-500">
            执行步骤 {planProgress.current}/{planProgress.total}
          </div>
        )}

        <div className="text-xs text-gray-400">
          {currentState === "DELIVERED"
            ? "项目已完成交付"
            : currentState === "FAILED"
            ? "执行遇到问题，工程师正在处理"
            : "系统调整中，请稍候"}
        </div>
      </div>

      {/* State timeline */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-sm font-medium text-gray-700 mb-4">执行阶段</h2>
        <div className="space-y-2">
          {Object.entries(STATE_LABELS)
            .filter(([, v]) => v.phase >= 0)
            .sort(([, a], [, b]) => a.phase - b.phase)
            .map(([state, info]) => (
              <div key={state} className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full shrink-0 ${
                  info.phase < stateInfo.phase ? "bg-gray-400" :
                  state === currentState ? "bg-gray-900" :
                  "bg-gray-200"
                }`} />
                <span className={`text-sm ${
                  state === currentState ? "text-gray-900 font-medium" :
                  info.phase < stateInfo.phase ? "text-gray-400" : "text-gray-300"
                }`}>
                  {info.label}
                </span>
              </div>
            ))}
        </div>
      </div>

      {/* Live log */}
      {logs.length > 0 && (
        <div className="bg-gray-900 rounded-2xl p-4 font-mono text-xs text-gray-300 max-h-48 overflow-y-auto">
          {logs.map((line, i) => <div key={i}>{line}</div>)}
          <div ref={logsEndRef} />
        </div>
      )}
    </div>
  )
}
