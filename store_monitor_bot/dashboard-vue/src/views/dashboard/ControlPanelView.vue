<template>
  <div class="control-panel">
    <h2>Control Panel</h2>

    <section class="card">
      <h3>Send Notification</h3>
      <label>Recipient</label>
      <input v-model.number="recipient" placeholder="123456789" />
      <label>Message</label>
      <textarea v-model="message" rows="3">Test notification from Control Panel</textarea>
      <div class="row">
        <button @click="sendNotification">Send</button>
        <button @click="testTelegram">Test Telegram</button>
      </div>
      <pre>{{ notifResult }}</pre>
    </section>

    <section class="card">
      <h3>System Health</h3>
      <button @click="refreshHealth">Refresh</button>
      <pre>{{ health }}</pre>
    </section>

    <section class="card">
      <h3>Tests</h3>
      <label>Scraper URL</label>
      <input v-model="testUrl" placeholder="https://example.com/p/1" />
      <label>Product ID (optional for queue)</label>
      <input v-model.number="testProductId" placeholder="42" />
      <div class="row">
        <button @click="runScraperInline">Run Scraper Inline</button>
        <button @click="queueScraper">Queue Scraper</button>
        <button @click="pingWorkers">Ping Workers</button>
      </div>
      <pre>{{ testResult }}</pre>
    </section>
  </div>
</template>

<script>
import { ref } from 'vue'
import api from '../../api/axios'

export default {
  name: 'ControlPanelView',
  setup() {
    const recipient = ref(0)
    const message = ref('')
    const notifResult = ref('Ready')
    const health = ref('Unknown')
    const testUrl = ref('')
    const testProductId = ref(null)
    const testResult = ref('Ready')

    const sendNotification = async () => {
      notifResult.value = 'Sending...'
      try {
        const res = await api.post('/api/notifications/send', { recipient: recipient.value, message: message.value, type: 'user' })
        notifResult.value = JSON.stringify(res.data, null, 2)
      } catch (e) { notifResult.value = e.toString() }
    }

    const testTelegram = async () => {
      notifResult.value = 'Queueing test...'
      try {
        const res = await api.post('/api/test/telegram', { telegram_id: recipient.value, message: 'Control panel test message' })
        notifResult.value = JSON.stringify(res.data, null, 2)
      } catch (e) { notifResult.value = e.toString() }
    }

    const refreshHealth = async () => {
      health.value = 'Checking...'
      try {
        const res = await api.get('/api/system/health')
        health.value = JSON.stringify(res.data, null, 2)
      } catch (e) { health.value = e.toString() }
    }

    const runScraperInline = async () => {
      testResult.value = 'Running...'
      try {
        const res = await api.post('/api/test/scraper', { url: testUrl.value })
        testResult.value = JSON.stringify(res.data, null, 2)
      } catch (e) { testResult.value = e.toString() }
    }

    const queueScraper = async () => {
      testResult.value = 'Queueing...'
      try {
        const res = await api.post('/api/test/scraper', { url: testUrl.value, product_id: testProductId.value })
        testResult.value = JSON.stringify(res.data, null, 2)
      } catch (e) { testResult.value = e.toString() }
    }

    const pingWorkers = async () => {
      testResult.value = 'Pinging...'
      try {
        const res = await api.post('/api/test/worker')
        testResult.value = JSON.stringify(res.data, null, 2)
      } catch (e) { testResult.value = e.toString() }
    }

    return {
      recipient, message, notifResult, health, testUrl, testProductId, testResult,
      sendNotification, testTelegram, refreshHealth, runScraperInline, queueScraper, pingWorkers,
    }
  }
}
</script>

<style scoped>
.card{background:#fff;border-radius:8px;padding:12px;margin-bottom:12px}
label{display:block;margin-top:8px}
input,textarea{width:100%;padding:8px;margin-top:6px}
button{padding:8px 12px;margin-right:6px}
pre{background:#0f172a;color:#e6fffa;padding:8px;border-radius:6px}
</style>
