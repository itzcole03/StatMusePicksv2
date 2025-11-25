import React, { useState, useRef, useEffect } from 'react'
import { streamOllamaAnalysis } from '../services/aiService.v2'

type Props = {
  model?: string
  initialPrompt?: string
}

export const StreamingAnalysis: React.FC<Props> = ({ model, initialPrompt = '' }) => {
  const [prompt, setPrompt] = useState<string>(initialPrompt)
  const [output, setOutput] = useState<string>('')
  const [streaming, setStreaming] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const pendingWordsRef = useRef<string[]>([])
  const applyingRef = useRef(false)

  useEffect(() => {
    let mounted = true
    const applyPending = async () => {
      if (applyingRef.current) return
      applyingRef.current = true
      while (mounted && pendingWordsRef.current.length > 0) {
        const w = pendingWordsRef.current.shift()
        if (w !== undefined) {
          setOutput((s) => (s ? s + ' ' + w : w))
          // slight throttle so words appear one-by-one
          // adjustable for UX
          await new Promise((r) => setTimeout(r, 30))
        }
      }
      applyingRef.current = false
    }

    const interval = setInterval(() => {
      if (pendingWordsRef.current.length > 0) applyPending()
    }, 50)

    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  const start = async () => {
    setOutput('')
    setError(null)
    setStreaming(true)
    const ac = new AbortController()
    abortRef.current = ac

    try {
      await streamOllamaAnalysis(
        prompt,
        { model, signal: ac.signal },
        (chunk) => {
            if (chunk.error) {
            setError(chunk.error)
            setStreaming(false)
            try {
              ac.abort()
            } catch {}
          }
          if (chunk.text) {
            // break incoming fragment into words to animate
            const words = String(chunk.text).split(/\s+/).filter(Boolean)
            pendingWordsRef.current.push(...words)
          }
          if (chunk.done) {
            setStreaming(false)
          }
        },
        () => setStreaming(false),
        (e) => {
          setError(String(e))
          setStreaming(false)
        }
      )
        } catch (err: any) {
          setError(String(err))
          setStreaming(false)
        }
  }

  const stop = () => {
    try {
      abortRef.current?.abort()
    } catch {}
    setStreaming(false)
  }

  return (
    <div className="p-4 bg-white rounded shadow">
      <div className="flex gap-2 mb-2">
        <input
          className="flex-1 border rounded px-2 py-1"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter analysis prompt..."
        />
        {!streaming ? (
          <button className="btn btn-primary px-3" onClick={start} disabled={!prompt}>
            Start
          </button>
        ) : (
          <button className="btn btn-secondary px-3" onClick={stop}>
            Stop
          </button>
        )}
      </div>

      <div className="min-h-[120px] border rounded p-3 bg-slate-50 text-sm whitespace-pre-wrap">
        {output || <span className="text-muted">Realtime analysis will appear here...</span>}
      </div>

      {error && <div className="text-red-600 mt-2">Error: {error}</div>}

      <div className="text-xs text-gray-500 mt-2">{streaming ? 'Streaming...' : 'Idle'}</div>
    </div>
  )
}

export default StreamingAnalysis
