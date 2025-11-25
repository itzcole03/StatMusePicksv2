import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import StreamingAnalysis from '../StreamingAnalysis'

// Mock the streamOllamaAnalysis helper to simulate streaming tokens
import { vi } from 'vitest'
vi.mock('../../services/aiService.v2', async () => {
  return {
    streamOllamaAnalysis: async (prompt: string, opts: any, onChunk: any, onDone: any, _onError: any) => {
      onChunk({ text: 'Hello' })
      await new Promise((r) => setTimeout(r, 10))
      onChunk({ text: 'world' })
      await new Promise((r) => setTimeout(r, 10))
      onChunk({ done: true })
      onDone()
    },
  }
})

describe('StreamingAnalysis', () => {
  it('renders and streams tokens', async () => {
    render(<StreamingAnalysis initialPrompt="test prompt" />)

    const startBtn = screen.getByRole('button', { name: /Start/i })
    expect(startBtn).toBeInTheDocument()

    fireEvent.click(startBtn)

    await waitFor(() => expect(screen.getByText(/Streaming.../i)).toBeInTheDocument())

    // wait for tokens to appear in output
    await waitFor(() => expect(screen.getByText(/Hello/)).toBeInTheDocument(), { timeout: 1000 })
    await waitFor(() => expect(screen.getByText(/world/)).toBeInTheDocument(), { timeout: 1000 })
  })
})
