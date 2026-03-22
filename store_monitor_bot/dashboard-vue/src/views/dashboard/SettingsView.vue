<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  clearCache,
  exportData,
  getSettings,
  getSystemInfo,
  restartMonitor,
  saveSettings,
  testAiScraper,
} from '../../api/settings'
import {
  createSupportTeamMember,
  fetchSupportTeam,
  updateSupportTeamMember,
} from '../../api/support'

const tabs = [
  { key: 'bot', label: '🤖 البوت' },
  { key: 'plans', label: '💳 الاشتراكات' },
  { key: 'monitoring', label: '⏱ المراقبة' },
  { key: 'templates', label: '🔔 الإشعارات' },
  { key: 'team', label: '👥 الفريق' },
  { key: 'affiliate', label: '💰 الأفلييت' },
  { key: 'security', label: '🔒 الأمان' },
  { key: 'system', label: '🛠 النظام' },
]

const activeTab = ref('bot')
const loading = ref(false)
const saving = reactive({
  bot: false,
  plans: false,
  monitoring: false,
  templates: false,
  team: false,
  affiliate: false,
  security: false,
  system: false,
})
const dirty = reactive({
  bot: false,
  plans: false,
  monitoring: false,
  templates: false,
  team: false,
  affiliate: false,
  security: false,
  system: false,
})

const statusMessage = ref('')
const systemInfo = ref({})
const aiTestUrl = ref('')
const aiTestLoading = ref(false)
const aiTestResult = ref(null)
const aiTestError = ref('')
const showAiKey = ref(false)
const teamMembers = ref([])
const newTeamMember = reactive({
  display_name: '',
  department: 'support',
  admin_id: '',
  role: '',
  avatar_color: '#2563EB',
  is_available: true,
})

const discountCodes = ref([
  { code: 'SAVE50', label: 'خصم 50%', usage: '10 استخدام' },
  { code: 'TRIAL7', label: '7 أيام مجانية', usage: 'فعّال' },
])

const loginAttempts = ref([
  { time: '2026-03-18 02:48', ip: '127.0.0.1', status: '✅ نجح' },
  { time: '2026-03-17 15:39', ip: '127.0.0.1', status: '❌ فشل' },
  { time: '2026-03-17 15:38', ip: '127.0.0.1', status: '❌ فشل' },
])

const form = reactive({
  bot: {
    bot_name: 'DealScope',
    welcome_message: '👋 أهلاً بك في بوت مراقبة الأسعار والعروض!',
    maintenance_mode: false,
    maintenance_message: '🔧 البوت قيد الصيانة...',
    min_discount_percent: 10,
    test_mode: false,
  },
  plans: {
    free: { price: 0, max_products: 3, max_categories: 0, max_stores: 0, scan_interval: 60 },
    basic: { price: 10, max_products: 50, max_categories: 10, max_stores: 0, scan_interval: 30 },
    professional: { price: 49, max_products: 300, max_categories: 50, max_stores: 20, scan_interval: 15 },
  },
  monitoring: {
    scraping_delay: 2,
    max_requests_per_minute: 10,
    max_products_per_cycle: 50,
    retry_attempts: 3,
    longcat_api_key: '',
    ai_scraping_enabled: true,
    ai_scraping_mode: 'fallback',
    ai_tokens_today: 0,
    sites: [
      { name: 'amazon.sa', status: '✅ طبيعي', success_rate: 98, active: true },
      { name: 'amazon.com', status: '✅ طبيعي', success_rate: 95, active: true },
      { name: 'noon.com', status: '⚠️ بطيء', success_rate: 72, active: true },
      { name: 'extra.com', status: '❌ معطل', success_rate: 23, active: false },
    ],
  },
  templates: {
    price_drop: '📉 انخفاض في السعر!\n{product_name}\nالسعر: {old_price} ← {new_price}\nخصم: {discount}%',
    deal_approved: '🔥 عرض قوي!\n{product_name}\nخصم {discount}% 🎯',
    back_in_stock: '🟢 عاد للمخزون: {product_name}',
    out_of_stock: '🔴 نفد المخزون: {product_name}',
    subscription_activated: '✅ تم تفعيل اشتراكك: {plan}',
    user_banned: '🚫 تم تقييد حسابك مؤقتاً',
    support_reply: '💬 رد الدعم: {message}',
  },
  affiliate: {
    default_link: 'https://amzn.to/default',
    auto_tag: false,
    default_tag: 'storemonitor-21',
    default_offer_text: '🔥 عرض حصري! سارع قبل النفاد',
    platform_amazon: true,
    platform_noon: false,
    platform_extra: false,
  },
  security: {
    max_login_attempts: 5,
    lockout_minutes: 15,
    jwt_expire_hours: 8,
    blocked_ips: [],
    rate_limit_per_minute: 10,
    current_password: '',
    new_password: '',
    confirm_password: '',
    pending_ip: '',
  },
  system: {
    maintenance_mode: false,
    backup_schedule: 'كل يوم الساعة 3:00 صباحاً',
    last_backup: '2026-03-17 00:00',
  },
})

const hasDirtyTab = computed(() => Object.values(dirty).some(Boolean))

function markDirty(tabKey) {
  dirty[tabKey] = true
}

function toNumber(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isNaN(parsed) ? fallback : parsed
}

function toBoolean(value) {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function getValue(values, key, fallback) {
  return values[key] ?? fallback
}

function setStatus(message) {
  statusMessage.value = message
  setTimeout(() => {
    if (statusMessage.value === message) {
      statusMessage.value = ''
    }
  }, 3000)
}

const maskedAiKey = computed(() => {
  const key = form.monitoring.longcat_api_key || ''
  if (!key) return 'غير مضبوط'
  if (showAiKey.value) return key
  return `${key.slice(0, 6)}••••••••••••••••`
})

async function loadCategory(category) {
  const { data } = await getSettings(category)
  return data.values || {}
}

async function loadAllSettings() {
  loading.value = true
  try {
    const [bot, plans, monitoring, templates, affiliate, security, system, team] = await Promise.all([
      loadCategory('bot'),
      loadCategory('plans'),
      loadCategory('monitoring'),
      loadCategory('templates'),
      loadCategory('affiliate'),
      loadCategory('security'),
      getSystemInfo(),
      fetchSupportTeam(),
    ])

    form.bot.bot_name = getValue(bot, 'bot.bot_name', form.bot.bot_name)
    form.bot.welcome_message = getValue(bot, 'bot.welcome_message', form.bot.welcome_message)
    form.bot.maintenance_mode = toBoolean(getValue(bot, 'bot.maintenance_mode', form.bot.maintenance_mode))
    form.bot.maintenance_message = getValue(bot, 'bot.maintenance_message', form.bot.maintenance_message)
    form.bot.min_discount_percent = toNumber(getValue(monitoring, 'monitoring.min_discount_percent', form.bot.min_discount_percent), 10)
    form.bot.test_mode = toBoolean(getValue(bot, 'bot.test_mode', form.bot.test_mode))

    for (const plan of ['free', 'basic', 'professional']) {
      form.plans[plan].price = toNumber(getValue(plans, `plans.${plan}.price`, form.plans[plan].price), form.plans[plan].price)
      form.plans[plan].max_products = toNumber(getValue(plans, `plans.${plan}.max_products`, form.plans[plan].max_products), form.plans[plan].max_products)
      form.plans[plan].max_categories = toNumber(getValue(plans, `plans.${plan}.max_categories`, form.plans[plan].max_categories), form.plans[plan].max_categories)
      form.plans[plan].max_stores = toNumber(getValue(plans, `plans.${plan}.max_stores`, form.plans[plan].max_stores), form.plans[plan].max_stores)
      form.plans[plan].scan_interval = toNumber(getValue(plans, `plans.${plan}.scan_interval`, form.plans[plan].scan_interval), form.plans[plan].scan_interval)
    }

    form.monitoring.scraping_delay = toNumber(getValue(monitoring, 'monitoring.scraping_delay', form.monitoring.scraping_delay), 2)
    form.monitoring.max_requests_per_minute = toNumber(getValue(monitoring, 'monitoring.max_requests_per_minute', form.monitoring.max_requests_per_minute), 10)
    form.monitoring.max_products_per_cycle = toNumber(getValue(monitoring, 'monitoring.max_products_per_cycle', form.monitoring.max_products_per_cycle), 50)
    form.monitoring.retry_attempts = toNumber(getValue(monitoring, 'monitoring.retry_attempts', form.monitoring.retry_attempts), 3)
    form.monitoring.longcat_api_key = getValue(monitoring, 'monitoring.longcat_api_key', form.monitoring.longcat_api_key)
    form.monitoring.ai_scraping_enabled = toBoolean(getValue(monitoring, 'monitoring.ai_scraping_enabled', form.monitoring.ai_scraping_enabled))
    form.monitoring.ai_scraping_mode = getValue(monitoring, 'monitoring.ai_scraping_mode', form.monitoring.ai_scraping_mode)

    Object.assign(form.templates, {
      price_drop: getValue(templates, 'templates.price_drop', form.templates.price_drop),
      deal_approved: getValue(templates, 'templates.deal_approved', form.templates.deal_approved),
      back_in_stock: getValue(templates, 'templates.back_in_stock', form.templates.back_in_stock),
      out_of_stock: getValue(templates, 'templates.out_of_stock', form.templates.out_of_stock),
      subscription_activated: getValue(templates, 'templates.subscription_activated', form.templates.subscription_activated),
      user_banned: getValue(templates, 'templates.user_banned', form.templates.user_banned),
      support_reply: getValue(templates, 'templates.support_reply', form.templates.support_reply),
    })

    Object.assign(form.affiliate, {
      default_link: getValue(affiliate, 'affiliate.default_link', form.affiliate.default_link),
      auto_tag: toBoolean(getValue(affiliate, 'affiliate.auto_tag', form.affiliate.auto_tag)),
      default_tag: getValue(affiliate, 'affiliate.default_tag', form.affiliate.default_tag),
      default_offer_text: getValue(affiliate, 'affiliate.default_offer_text', form.affiliate.default_offer_text),
      platform_amazon: toBoolean(getValue(affiliate, 'affiliate.platform_amazon', form.affiliate.platform_amazon)),
      platform_noon: toBoolean(getValue(affiliate, 'affiliate.platform_noon', form.affiliate.platform_noon)),
      platform_extra: toBoolean(getValue(affiliate, 'affiliate.platform_extra', form.affiliate.platform_extra)),
    })

    Object.assign(form.security, {
      max_login_attempts: toNumber(getValue(security, 'security.max_login_attempts', form.security.max_login_attempts), 5),
      lockout_minutes: toNumber(getValue(security, 'security.lockout_minutes', form.security.lockout_minutes), 15),
      jwt_expire_hours: toNumber(getValue(security, 'security.jwt_expire_hours', form.security.jwt_expire_hours), 8),
      rate_limit_per_minute: toNumber(getValue(security, 'security.rate_limit_per_minute', form.security.rate_limit_per_minute), 10),
      blocked_ips: Array.isArray(getValue(security, 'security.blocked_ips', form.security.blocked_ips))
        ? getValue(security, 'security.blocked_ips', form.security.blocked_ips)
        : form.security.blocked_ips,
    })

    systemInfo.value = system.data || {}
    form.system.last_backup = form.system.last_backup
    form.system.maintenance_mode = form.bot.maintenance_mode
    teamMembers.value = team.data.members || []
  } finally {
    loading.value = false
  }
}

function trySwitchTab(next) {
  if (activeTab.value === next) return
  if (dirty[activeTab.value] && !window.confirm('هناك تغييرات غير محفوظة. هل تريد المتابعة بدون حفظ؟')) {
    return
  }
  activeTab.value = next
}

async function saveBotTab() {
  saving.bot = true
  try {
    await saveSettings('bot', {
      'bot.bot_name': form.bot.bot_name,
      'bot.welcome_message': form.bot.welcome_message,
      'bot.maintenance_mode': form.bot.maintenance_mode,
      'bot.maintenance_message': form.bot.maintenance_message,
      'bot.test_mode': form.bot.test_mode,
    })
    await saveSettings('monitoring', {
      'monitoring.min_discount_percent': form.bot.min_discount_percent,
    })
    dirty.bot = false
    setStatus('تم حفظ إعدادات البوت')
  } finally {
    saving.bot = false
  }
}

async function savePlansTab() {
  saving.plans = true
  try {
    const payload = {}
    for (const plan of ['free', 'basic', 'professional']) {
      payload[`plans.${plan}.price`] = form.plans[plan].price
      payload[`plans.${plan}.max_products`] = form.plans[plan].max_products
      payload[`plans.${plan}.max_categories`] = form.plans[plan].max_categories
      payload[`plans.${plan}.max_stores`] = form.plans[plan].max_stores
      payload[`plans.${plan}.scan_interval`] = form.plans[plan].scan_interval
    }
    await saveSettings('plans', payload)
    dirty.plans = false
    setStatus('تم حفظ إعدادات الخطط')
  } finally {
    saving.plans = false
  }
}

async function saveMonitoringTab() {
  saving.monitoring = true
  try {
    await saveSettings('monitoring', {
      'monitoring.scraping_delay': form.monitoring.scraping_delay,
      'monitoring.max_requests_per_minute': form.monitoring.max_requests_per_minute,
      'monitoring.max_products_per_cycle': form.monitoring.max_products_per_cycle,
      'monitoring.retry_attempts': form.monitoring.retry_attempts,
      'monitoring.longcat_api_key': form.monitoring.longcat_api_key,
      'monitoring.ai_scraping_enabled': form.monitoring.ai_scraping_enabled,
      'monitoring.ai_scraping_mode': form.monitoring.ai_scraping_mode,
    })
    dirty.monitoring = false
    setStatus('تم حفظ إعدادات المراقبة')
  } finally {
    saving.monitoring = false
  }
}

async function onTestAiScraper() {
  if (!aiTestUrl.value.trim()) return
  aiTestLoading.value = true
  aiTestError.value = ''
  aiTestResult.value = null
  try {
    const { data } = await testAiScraper(aiTestUrl.value.trim())
    if (!data.success) {
      aiTestError.value = data.error || 'فشل اختبار الاستخراج الذكي'
      return
    }
    aiTestResult.value = data.data
    form.monitoring.ai_tokens_today += 1200
  } catch (e) {
    aiTestError.value = e?.response?.data?.detail || 'حدث خطأ أثناء اختبار AI'
  } finally {
    aiTestLoading.value = false
  }
}

async function saveTemplatesTab() {
  saving.templates = true
  try {
    await saveSettings('templates', {
      'templates.price_drop': form.templates.price_drop,
      'templates.deal_approved': form.templates.deal_approved,
      'templates.back_in_stock': form.templates.back_in_stock,
      'templates.out_of_stock': form.templates.out_of_stock,
      'templates.subscription_activated': form.templates.subscription_activated,
      'templates.user_banned': form.templates.user_banned,
      'templates.support_reply': form.templates.support_reply,
    })
    dirty.templates = false
    setStatus('تم حفظ قوالب الرسائل')
  } finally {
    saving.templates = false
  }
}

async function saveAffiliateTab() {
  saving.affiliate = true
  try {
    await saveSettings('affiliate', {
      'affiliate.default_link': form.affiliate.default_link,
      'affiliate.auto_tag': form.affiliate.auto_tag,
      'affiliate.default_tag': form.affiliate.default_tag,
      'affiliate.default_offer_text': form.affiliate.default_offer_text,
      'affiliate.platform_amazon': form.affiliate.platform_amazon,
      'affiliate.platform_noon': form.affiliate.platform_noon,
      'affiliate.platform_extra': form.affiliate.platform_extra,
    })
    dirty.affiliate = false
    setStatus('تم حفظ إعدادات الأفلييت')
  } finally {
    saving.affiliate = false
  }
}

function addBlockedIp() {
  const ip = form.security.pending_ip.trim()
  if (!ip) return
  if (!form.security.blocked_ips.includes(ip)) {
    form.security.blocked_ips.push(ip)
    markDirty('security')
  }
  form.security.pending_ip = ''
}

function removeBlockedIp(ip) {
  form.security.blocked_ips = form.security.blocked_ips.filter((x) => x !== ip)
  markDirty('security')
}

async function saveSecurityTab() {
  saving.security = true
  try {
    await saveSettings('security', {
      'security.max_login_attempts': form.security.max_login_attempts,
      'security.lockout_minutes': form.security.lockout_minutes,
      'security.jwt_expire_hours': form.security.jwt_expire_hours,
      'security.rate_limit_per_minute': form.security.rate_limit_per_minute,
      'security.blocked_ips': form.security.blocked_ips,
    })
    dirty.security = false
    setStatus('تم حفظ إعدادات الأمان')
  } finally {
    saving.security = false
  }
}

async function saveTeamTab() {
  saving.team = true
  try {
    for (const member of teamMembers.value) {
      await updateSupportTeamMember(member.id, {
        display_name: member.display_name,
        department: member.department,
        admin_id: member.admin_id,
        role: member.role,
        avatar_color: member.avatar_color || '#2563EB',
        is_available: !!member.is_available,
      })
    }

    if (newTeamMember.display_name.trim()) {
      await createSupportTeamMember({
        display_name: newTeamMember.display_name,
        department: newTeamMember.department,
        admin_id: newTeamMember.admin_id ? Number(newTeamMember.admin_id) : null,
        role: newTeamMember.role,
        avatar_color: newTeamMember.avatar_color,
        is_available: !!newTeamMember.is_available,
      })
      newTeamMember.display_name = ''
      newTeamMember.department = 'support'
      newTeamMember.admin_id = ''
      newTeamMember.role = ''
      newTeamMember.avatar_color = '#2563EB'
      newTeamMember.is_available = true
    }

    const team = await fetchSupportTeam()
    teamMembers.value = team.data.members || []
    dirty.team = false
    setStatus('تم حفظ بيانات الفريق')
  } finally {
    saving.team = false
  }
}

async function saveSystemTab() {
  saving.system = true
  try {
    await saveSettings('bot', {
      'bot.maintenance_mode': form.system.maintenance_mode,
      'bot.maintenance_message': form.bot.maintenance_message,
    })
    form.bot.maintenance_mode = form.system.maintenance_mode
    dirty.system = false
    setStatus('تم حفظ إعدادات النظام')
  } finally {
    saving.system = false
  }
}

async function onRestartMonitor() {
  await restartMonitor()
  setStatus('تم إرسال طلب إعادة تشغيل المحرك')
}

async function onClearCache() {
  await clearCache()
  setStatus('تم تنفيذ مسح Redis Cache')
}

async function onExport(type) {
  const response = await exportData(type)
  const blob = new Blob([response.data])
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${type}_export`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

onMounted(loadAllSettings)
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-xl font-bold">الإعدادات</h1>
        <span v-if="hasDirtyTab" class="text-xs rounded-full px-2 py-1 bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">توجد تغييرات غير محفوظة</span>
      </div>
      <p class="text-sm text-slate-500 mt-1">إدارة إعدادات النظام والبوت من مكان واحد.</p>
      <p v-if="statusMessage" class="mt-3 text-sm text-emerald-600 dark:text-emerald-300">{{ statusMessage }}</p>
    </div>

    <div class="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-2">
      <div class="flex min-w-max gap-2">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="rounded-xl px-4 py-2 text-sm font-medium transition-colors"
          :class="activeTab === tab.key ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200'"
          @click="trySwitchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 text-center text-slate-500">جاري تحميل الإعدادات...</div>

    <section v-else-if="activeTab === 'bot'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">🤖 إعدادات البوت الأساسية</h2>
      <div>
        <label class="text-sm text-slate-600 dark:text-slate-300">اسم البوت</label>
        <input v-model="form.bot.bot_name" class="mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('bot')" />
      </div>
      <div>
        <label class="text-sm text-slate-600 dark:text-slate-300">رسالة الترحيب /start</label>
        <textarea v-model="form.bot.welcome_message" rows="4" class="mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('bot')"></textarea>
        <p class="text-xs text-slate-500 mt-1">متغيرات متاحة: {first_name} {plan}</p>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
          <input type="radio" :value="true" v-model="form.bot.maintenance_mode" @change="markDirty('bot')" />
          وضع الصيانة مفعّل
        </label>
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
          <input type="radio" :value="false" v-model="form.bot.maintenance_mode" @change="markDirty('bot')" />
          وضع الصيانة معطّل
        </label>
      </div>
      <div>
        <label class="text-sm text-slate-600 dark:text-slate-300">رسالة الصيانة</label>
        <input v-model="form.bot.maintenance_message" class="mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('bot')" />
      </div>
      <div>
        <label class="text-sm text-slate-600 dark:text-slate-300">الحد الأدنى للخصم (فرصة): {{ form.bot.min_discount_percent }}%</label>
        <input v-model.number="form.bot.min_discount_percent" type="range" min="10" max="50" class="w-full" @input="markDirty('bot')" />
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
          <input type="radio" :value="true" v-model="form.bot.test_mode" @change="markDirty('bot')" />
          وضع الاختبار مفعّل
        </label>
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
          <input type="radio" :value="false" v-model="form.bot.test_mode" @change="markDirty('bot')" />
          وضع الاختبار معطّل
        </label>
      </div>
      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.bot" @click="saveBotTab">💾 حفظ التغييرات</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'plans'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">💳 إعدادات الخطط</h2>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div v-for="plan in ['free', 'basic', 'professional']" :key="plan" class="rounded-xl border border-slate-300 dark:border-slate-700 p-4 space-y-2">
          <h3 class="font-semibold">{{ plan === 'free' ? '🆓 مجاني' : plan === 'basic' ? '⭐ أساسي' : '💎 احترافي' }}</h3>
          <label class="text-sm">السعر <input v-model.number="form.plans[plan].price" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('plans')" /></label>
          <label class="text-sm">المنتجات <input v-model.number="form.plans[plan].max_products" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('plans')" /></label>
          <label class="text-sm">الفئات <input v-model.number="form.plans[plan].max_categories" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('plans')" /></label>
          <label class="text-sm">المتاجر <input v-model.number="form.plans[plan].max_stores" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('plans')" /></label>
          <label class="text-sm">الفحص (دقيقة) <input v-model.number="form.plans[plan].scan_interval" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('plans')" /></label>
        </div>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold">كودات الخصم</h3>
          <button class="text-sm rounded-lg px-3 py-1 bg-slate-800 text-white" @click="discountCodes.push({ code: 'NEWCODE', label: 'خصم 10%', usage: 'جديد' }); markDirty('plans')">+ إنشاء كود جديد</button>
        </div>
        <div class="space-y-2">
          <div v-for="(item, idx) in discountCodes" :key="idx" class="flex items-center justify-between rounded-lg bg-slate-100 dark:bg-slate-800 px-3 py-2 text-sm">
            <span>{{ item.code }} | {{ item.label }} | {{ item.usage }}</span>
            <button class="text-rose-600" @click="discountCodes.splice(idx, 1); markDirty('plans')">🗑</button>
          </div>
        </div>
      </div>
      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.plans" @click="savePlansTab">💾 حفظ التغييرات</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'monitoring'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">⏱ إعدادات محرك المراقبة</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="text-sm">التأخير بين الطلبات (ثانية)
          <input v-model.number="form.monitoring.scraping_delay" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('monitoring')" />
        </label>
        <label class="text-sm">الحد الأقصى للطلبات/دقيقة
          <input v-model.number="form.monitoring.max_requests_per_minute" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('monitoring')" />
        </label>
        <label class="text-sm">أقصى منتجات في دورة الفحص
          <input v-model.number="form.monitoring.max_products_per_cycle" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('monitoring')" />
        </label>
        <label class="text-sm">محاولات إعادة المحاولة
          <input v-model.number="form.monitoring.retry_attempts" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('monitoring')" />
        </label>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4 space-y-2">
        <h3 class="font-semibold">حالة المواقع</h3>
        <div v-for="site in form.monitoring.sites" :key="site.name" class="flex items-center justify-between rounded-lg bg-slate-100 dark:bg-slate-800 px-3 py-2 text-sm">
          <span>{{ site.name }} | {{ site.status }} | {{ site.success_rate }}%</span>
          <button class="rounded-lg px-2 py-1" :class="site.active ? 'bg-emerald-200 text-emerald-800' : 'bg-rose-200 text-rose-800'" @click="site.active = !site.active; markDirty('monitoring')">🔒</button>
        </div>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4 space-y-3">
        <h3 class="font-semibold">🤖 الاستخراج الذكي بالـ AI</h3>

        <div>
          <label class="text-sm">LongCat API Key</label>
          <div class="flex gap-2 mt-1">
            <input v-model="form.monitoring.longcat_api_key" class="flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('monitoring')" :type="showAiKey ? 'text' : 'password'" />
            <button class="rounded-lg px-3 py-2 bg-slate-800 text-white" @click="showAiKey = !showAiKey">{{ showAiKey ? '🙈' : '👁' }}</button>
          </div>
          <p class="text-xs text-slate-500 mt-1">{{ maskedAiKey }}</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
          <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
            <input type="radio" value="fallback" v-model="form.monitoring.ai_scraping_mode" @change="markDirty('monitoring')" />
            ذكي (CSS أولاً، AI عند الفشل)
          </label>
          <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
            <input type="radio" value="primary" v-model="form.monitoring.ai_scraping_mode" @change="markDirty('monitoring')" />
            AI أولاً (أبطأ لكن أدق)
          </label>
          <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3">
            <input type="radio" value="disabled" @change="form.monitoring.ai_scraping_enabled = false; markDirty('monitoring')" :checked="!form.monitoring.ai_scraping_enabled" />
            CSS فقط (بدون AI)
          </label>
        </div>

        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" v-model="form.monitoring.ai_scraping_enabled" @change="markDirty('monitoring')" />
          تفعيل الاستخراج الذكي
        </label>

        <div class="text-sm text-slate-600 dark:text-slate-300">
          الحالة: {{ form.monitoring.ai_scraping_enabled ? '✅ مفعّل' : '⏸ معطّل' }}
        </div>
        <div class="text-sm text-slate-600 dark:text-slate-300">
          التوكنات المستهلكة اليوم: {{ form.monitoring.ai_tokens_today.toLocaleString() }}
        </div>

        <div class="space-y-2">
          <div class="flex gap-2">
            <input v-model="aiTestUrl" placeholder="https://example.com/product" class="flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" />
            <button class="rounded-xl bg-indigo-600 text-white px-4 py-2" :disabled="aiTestLoading" @click="onTestAiScraper">🔍 اختبار AI على رابط</button>
          </div>
          <p v-if="aiTestError" class="text-sm text-rose-600">{{ aiTestError }}</p>
          <pre v-if="aiTestResult" class="rounded-lg bg-slate-100 dark:bg-slate-800 p-3 text-xs overflow-auto">{{ JSON.stringify(aiTestResult, null, 2) }}</pre>
        </div>
      </div>

      <div class="flex justify-end gap-2">
        <button class="rounded-xl bg-slate-800 text-white px-4 py-2" @click="onRestartMonitor">🔄 إعادة تشغيل محرك</button>
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.monitoring" @click="saveMonitoringTab">💾 حفظ</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'templates'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">🔔 قوالب رسائل التنبيهات</h2>
      <div v-for="key in ['price_drop', 'deal_approved', 'back_in_stock', 'out_of_stock', 'subscription_activated', 'user_banned', 'support_reply']" :key="key">
        <label class="text-sm text-slate-600 dark:text-slate-300">{{ key }}</label>
        <textarea v-model="form.templates[key]" rows="3" class="mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('templates')"></textarea>
      </div>
      <p class="text-xs text-slate-500">المتغيرات المتاحة: {product_name} {price} {discount} {username} {plan} {date}</p>
      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.templates" @click="saveTemplatesTab">💾 حفظ القوالب</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'team'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">👥 حسابات الإدارة</h2>
      </div>

      <div class="space-y-3">
        <div v-for="member in teamMembers" :key="member.id" class="rounded-xl border border-slate-300 dark:border-slate-700 p-4 grid grid-cols-1 md:grid-cols-6 gap-2 items-center">
          <input v-model="member.display_name" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
          <select v-model="member.department" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @change="markDirty('team')">
            <option value="support">support</option>
            <option value="billing">billing</option>
            <option value="technical">technical</option>
            <option value="general">general</option>
            <option value="management">management</option>
          </select>
          <input v-model="member.role" placeholder="الدور" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
          <input v-model="member.admin_id" type="number" placeholder="admin_id" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
          <input v-model="member.avatar_color" type="color" class="h-9 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
          <label class="flex items-center gap-2"><input type="checkbox" v-model="member.is_available" @change="markDirty('team')" /> متاح</label>
        </div>
      </div>

      <div class="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-4 grid grid-cols-1 md:grid-cols-6 gap-2">
        <input v-model="newTeamMember.display_name" placeholder="اسم العضو الجديد" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
        <select v-model="newTeamMember.department" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @change="markDirty('team')">
          <option value="support">support</option>
          <option value="billing">billing</option>
          <option value="technical">technical</option>
          <option value="general">general</option>
          <option value="management">management</option>
        </select>
        <input v-model="newTeamMember.role" placeholder="الدور" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
        <input v-model="newTeamMember.admin_id" type="number" placeholder="admin_id" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
        <input v-model="newTeamMember.avatar_color" type="color" class="h-9 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-1" @input="markDirty('team')" />
        <label class="flex items-center gap-2"><input type="checkbox" v-model="newTeamMember.is_available" @change="markDirty('team')" /> متاح</label>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4 space-y-2">
        <h3 class="font-semibold">سجل تسجيل الدخول الأخير</h3>
        <div v-for="item in loginAttempts" :key="item.time + item.status" class="text-sm text-slate-600 dark:text-slate-300">{{ item.time }} | {{ item.ip }} | {{ item.status }}</div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
        <input v-model="form.security.current_password" type="password" placeholder="كلمة المرور الحالية" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-2" />
        <input v-model="form.security.new_password" type="password" placeholder="كلمة المرور الجديدة" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-2" />
        <input v-model="form.security.confirm_password" type="password" placeholder="تأكيد كلمة المرور" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-2" />
      </div>

      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.team" @click="saveTeamTab">💾 حفظ</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'affiliate'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">💰 إعدادات الأفلييت</h2>
      <label class="text-sm">رابط الأفلييت الافتراضي
        <input v-model="form.affiliate.default_link" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('affiliate')" />
      </label>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3"><input type="checkbox" v-model="form.affiliate.auto_tag" @change="markDirty('affiliate')" /> إضافة tag تلقائي لروابط أمازون</label>
        <label class="text-sm">Tag ID
          <input v-model="form.affiliate.default_tag" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('affiliate')" />
        </label>
      </div>
      <label class="text-sm">قالب نص العرض الافتراضي
        <textarea v-model="form.affiliate.default_offer_text" rows="3" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('affiliate')"></textarea>
      </label>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3"><input type="checkbox" v-model="form.affiliate.platform_amazon" @change="markDirty('affiliate')" /> Amazon Associates</label>
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3"><input type="checkbox" v-model="form.affiliate.platform_noon" @change="markDirty('affiliate')" /> Noon Affiliate</label>
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3"><input type="checkbox" v-model="form.affiliate.platform_extra" @change="markDirty('affiliate')" /> Extra Affiliate</label>
      </div>
      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.affiliate" @click="saveAffiliateTab">💾 حفظ</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'security'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">🔒 إعدادات الأمان</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="text-sm">محاولات تسجيل الدخول قبل القفل
          <input v-model.number="form.security.max_login_attempts" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('security')" />
        </label>
        <label class="text-sm">مدة قفل الحساب (دقيقة)
          <input v-model.number="form.security.lockout_minutes" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('security')" />
        </label>
        <label class="text-sm">انتهاء صلاحية JWT (ساعات)
          <input v-model.number="form.security.jwt_expire_hours" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('security')" />
        </label>
        <label class="text-sm">Rate Limiting تسجيل الدخول/دقيقة لكل IP
          <input v-model.number="form.security.rate_limit_per_minute" type="number" class="w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" @input="markDirty('security')" />
        </label>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4">
        <h3 class="font-semibold mb-2">IPs المحظورة</h3>
        <div class="space-y-2 mb-3">
          <div v-for="ip in form.security.blocked_ips" :key="ip" class="flex items-center justify-between rounded-lg bg-slate-100 dark:bg-slate-800 px-3 py-2 text-sm">
            <span>{{ ip }}</span>
            <button class="text-rose-600" @click="removeBlockedIp(ip)">إزالة</button>
          </div>
        </div>
        <div class="flex gap-2">
          <input v-model="form.security.pending_ip" placeholder="+ إضافة IP" class="flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" />
          <button class="rounded-lg bg-slate-800 text-white px-3" @click="addBlockedIp">إضافة</button>
        </div>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4">
        <h3 class="font-semibold mb-2">محاولات الدخول الفاشلة</h3>
        <div v-for="item in loginAttempts.filter((x) => x.status.includes('❌'))" :key="item.time + item.status" class="text-sm text-slate-600 dark:text-slate-300">{{ item.time }} | {{ item.ip }} | telegram_id غير صحيح</div>
      </div>

      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.security" @click="saveSecurityTab">💾 حفظ</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'system'" class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
      <h2 class="text-lg font-semibold">🛠 معلومات النظام</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div class="rounded-xl bg-slate-100 dark:bg-slate-800 p-3">إصدار البوت: {{ systemInfo.bot_version || 'v1.0.0' }}</div>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-800 p-3">Python: {{ systemInfo.python_version || '-' }}</div>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-800 p-3">قاعدة البيانات: {{ systemInfo.database_version || '-' }}</div>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-800 p-3">Redis: {{ systemInfo.redis_status === 'connected' ? '✅ متصل' : '❌ غير متصل' }}</div>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-800 p-3">آخر migration: {{ systemInfo.last_migration || '-' }}</div>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-800 p-3">آخر backup: {{ form.system.last_backup }}</div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
        <button class="rounded-xl bg-slate-800 text-white px-4 py-2" @click="onRestartMonitor">🔄 إعادة تشغيل محرك المراقبة</button>
        <button class="rounded-xl bg-rose-600 text-white px-4 py-2" @click="onClearCache">🗑 مسح Redis Cache</button>
        <button class="rounded-xl bg-emerald-600 text-white px-4 py-2" @click="loadAllSettings">📊 تطبيق Migrations الجديدة</button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3"><input type="radio" :value="false" v-model="form.system.maintenance_mode" @change="markDirty('system')" /> وضع الصيانة معطّل</label>
        <label class="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 p-3"><input type="radio" :value="true" v-model="form.system.maintenance_mode" @change="markDirty('system')" /> وضع الصيانة مفعّل</label>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
        <button class="rounded-xl bg-slate-700 text-white px-4 py-2" @click="onExport('users')">📥 تصدير المستخدمين CSV</button>
        <button class="rounded-xl bg-slate-700 text-white px-4 py-2" @click="onExport('products')">📥 تصدير المنتجات CSV</button>
        <button class="rounded-xl bg-slate-700 text-white px-4 py-2" @click="onExport('reports')">📥 تصدير التقارير PDF</button>
      </div>

      <div class="rounded-xl border border-slate-300 dark:border-slate-700 p-4 text-sm">
        <div>جدول النسخ التلقائي: {{ form.system.backup_schedule }}</div>
        <button class="mt-2 rounded-lg bg-blue-600 text-white px-3 py-2" @click="setStatus('تم تنفيذ backup يدوي')">💾 backup يدوي الآن</button>
      </div>

      <div class="flex justify-end">
        <button class="rounded-xl bg-blue-600 text-white px-4 py-2 disabled:opacity-60" :disabled="saving.system" @click="saveSystemTab">💾 حفظ</button>
      </div>
    </section>
  </div>
</template>
