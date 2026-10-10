import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { HealthPayload } from '../lib/api'

const okDisabled: HealthPayload = {
  status: 'ok',
  service: 'factora',
  version: '0.1.0',
  environment: 'development',
  time_utc: '2026-01-01T00:00:00Z',
  uptime_s: 12,
  observability: {
    provider: 'neatlogs',
    status: 'disabled',
    detail: 'NEATLOGS_API_KEY not set - observability disabled (app runs normally)',
  },
}

describe('BackendStatus', () => {
  it('renders backend reachable with observability disabled honestly', async () => {
    vi.doMock('../lib/api', async (importOriginal) => {
      const actual = await importOriginal<typeof import('../lib/api')>()
      return { ...actual, fetchHealth: () => Promise.resolve(okDisabled) }
    })
    vi.resetModules()

    const { default: Fresh } = await import('./BackendStatus')
    render(<Fresh />)

    await waitFor(() => expect(screen.getByText('Backend reachable')).toBeInTheDocument())
    expect(screen.getByText('neatlogs', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Tracing')).toBeInTheDocument()
    expect(screen.getByText('disabled')).toBeInTheDocument()
  })
})
