import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'

import App from './App.vue'
import router from './router'
import './index.css'
import { vTooltip } from './directives/tooltip'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(Toast, {
	rtl: true,
	position: 'bottom-center',
	timeout: 3000,
})
app.directive('tooltip', vTooltip)

app.mount('#app')
