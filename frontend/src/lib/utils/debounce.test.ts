import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { debounce } from './debounce'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('debounce', () => {
  it('calls the function after the delay', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    expect(fn).not.toHaveBeenCalled()

    vi.advanceTimersByTime(100)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('resets the timer on repeated calls', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    vi.advanceTimersByTime(50)
    debounced()
    vi.advanceTimersByTime(50)
    expect(fn).not.toHaveBeenCalled()

    vi.advanceTimersByTime(50)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('passes arguments to the wrapped function', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 50)

    debounced('a', 'b')
    vi.advanceTimersByTime(50)
    expect(fn).toHaveBeenCalledWith('a', 'b')
  })

  it('uses the last call arguments when called multiple times', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced('first')
    debounced('second')
    debounced('third')
    vi.advanceTimersByTime(100)
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('third')
  })
})
