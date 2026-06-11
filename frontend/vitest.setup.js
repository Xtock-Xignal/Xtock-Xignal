import '@testing-library/jest-dom'

const originalConsoleWarn = console.warn

console.warn = (...args) => {
  const message = String(args[0] ?? '')
  if (
    message.includes('of chart should be greater than 0') &&
    message.includes('please check the style of container')
  ) {
    return
  }
  originalConsoleWarn(...args)
}

class ResizeObserver {
  constructor(callback) {
    this.callback = callback
  }

  observe() {}
  unobserve() {}
  disconnect() {}
}

global.ResizeObserver = ResizeObserver

Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
  configurable: true,
  value: 800,
})

Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
  configurable: true,
  value: 380,
})

HTMLElement.prototype.getBoundingClientRect = function getBoundingClientRect() {
  return {
    width: 800,
    height: 380,
    top: 0,
    left: 0,
    bottom: 380,
    right: 800,
    x: 0,
    y: 0,
    toJSON() {},
  }
}
