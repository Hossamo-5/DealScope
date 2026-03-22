let tooltipEl = null
let tooltipTimer = null

const GAP = 8
const VIEWPORT_PADDING = 8
const SHOW_DELAY_MS = 200

function getBindingValue(binding) {
  if (typeof binding.value === 'string') {
    return { text: binding.value, position: 'top' }
  }
  return {
    text: binding.value?.text || '',
    position: binding.value?.position || 'top',
  }
}

function clearTimer() {
  if (tooltipTimer) {
    clearTimeout(tooltipTimer)
    tooltipTimer = null
  }
}

function hideTooltip() {
  clearTimer()
  if (tooltipEl) {
    tooltipEl.remove()
    tooltipEl = null
  }
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function placeTooltip(el, position) {
  const rect = el.getBoundingClientRect()
  const tipRect = tooltipEl.getBoundingClientRect()
  const viewportW = window.innerWidth
  const viewportH = window.innerHeight

  const candidates = {
    top: {
      top: rect.top - tipRect.height - GAP,
      left: rect.left + rect.width / 2 - tipRect.width / 2,
    },
    bottom: {
      top: rect.bottom + GAP,
      left: rect.left + rect.width / 2 - tipRect.width / 2,
    },
    right: {
      top: rect.top + rect.height / 2 - tipRect.height / 2,
      left: rect.right + GAP,
    },
    left: {
      top: rect.top + rect.height / 2 - tipRect.height / 2,
      left: rect.left - tipRect.width - GAP,
    },
  }

  let pos = candidates[position] || candidates.top

  if (pos.top < VIEWPORT_PADDING && position === 'top') pos = candidates.bottom
  if (pos.top + tipRect.height > viewportH - VIEWPORT_PADDING && position === 'bottom') pos = candidates.top
  if (pos.left < VIEWPORT_PADDING && position === 'left') pos = candidates.right
  if (pos.left + tipRect.width > viewportW - VIEWPORT_PADDING && position === 'right') pos = candidates.left

  pos.top = clamp(pos.top, VIEWPORT_PADDING, viewportH - tipRect.height - VIEWPORT_PADDING)
  pos.left = clamp(pos.left, VIEWPORT_PADDING, viewportW - tipRect.width - VIEWPORT_PADDING)

  tooltipEl.style.top = `${Math.round(pos.top)}px`
  tooltipEl.style.left = `${Math.round(pos.left)}px`
}

function showTooltip(el, text, position) {
  if (!text) return
  hideTooltip()

  tooltipTimer = setTimeout(() => {
    tooltipEl = document.createElement('div')
    tooltipEl.className = 'fixed z-[9999] px-2.5 py-1.5 text-xs font-medium rounded-lg shadow-lg pointer-events-none max-w-xs transition-opacity duration-150 bg-slate-900 text-white'
    tooltipEl.style.whiteSpace = 'normal'
    tooltipEl.style.direction = 'rtl'
    tooltipEl.style.textAlign = 'right'
    tooltipEl.textContent = text
    document.body.appendChild(tooltipEl)
    placeTooltip(el, position)
  }, SHOW_DELAY_MS)
}

export const vTooltip = {
  mounted(el, binding) {
    const { text, position } = getBindingValue(binding)
    el._tooltip = { text, position }

    el._showTooltip = () => showTooltip(el, el._tooltip.text, el._tooltip.position)
    el._hideTooltip = () => hideTooltip()

    el.addEventListener('mouseenter', el._showTooltip)
    el.addEventListener('mouseleave', el._hideTooltip)
    el.addEventListener('click', el._hideTooltip)
    el.addEventListener('blur', el._hideTooltip)
  },

  updated(el, binding) {
    const { text, position } = getBindingValue(binding)
    if (!el._tooltip) {
      el._tooltip = { text, position }
      return
    }
    el._tooltip.text = text
    el._tooltip.position = position
  },

  unmounted(el) {
    el.removeEventListener('mouseenter', el._showTooltip)
    el.removeEventListener('mouseleave', el._hideTooltip)
    el.removeEventListener('click', el._hideTooltip)
    el.removeEventListener('blur', el._hideTooltip)
    hideTooltip()
  },
}
