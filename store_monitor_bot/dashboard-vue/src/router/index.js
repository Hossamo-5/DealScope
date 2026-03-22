import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

import LoginView from '../views/LoginView.vue'
import DashboardLayout from '../views/dashboard/DashboardLayout.vue'
import HomeView from '../views/dashboard/HomeView.vue'
import OpportunitiesView from '../views/dashboard/OpportunitiesView.vue'
import UsersView from '../views/dashboard/UsersView.vue'
import UserProfileView from '../views/dashboard/UserProfileView.vue'
import SupportView from '../views/dashboard/SupportView.vue'
import SupportTeamView from '../views/dashboard/SupportTeamView.vue'
import StoresView from '../views/dashboard/StoresView.vue'
import StoreRequestsView from '../views/dashboard/StoreRequestsView.vue'
import HealthView from '../views/dashboard/HealthView.vue'
import ControlPanelView from '../views/dashboard/ControlPanelView.vue'
import NotificationsView from '../views/dashboard/NotificationsView.vue'
import SettingsView from '../views/dashboard/SettingsView.vue'
import MenuBuilderView from '../views/dashboard/MenuBuilderView.vue'
import IdResolverView from '../views/dashboard/IdResolverView.vue'
import GroupsView from '../views/dashboard/GroupsView.vue'
import BotsView from '../views/dashboard/BotsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/',
      component: DashboardLayout,
      children: [
        { path: '', name: 'home', component: HomeView },
        { path: 'opportunities', name: 'opportunities', component: OpportunitiesView },
        { path: 'users', name: 'users', component: UsersView },
        { path: 'users/:telegram_id', name: 'user-profile', component: UserProfileView },
        { path: 'support/:ticketId?', name: 'support', component: SupportView },
        { path: 'support/team', name: 'support-team', component: SupportTeamView },
        { path: 'stores', name: 'stores', component: StoresView },
        { path: 'store-requests', name: 'store-requests', component: StoreRequestsView },
        { path: 'menu-builder', name: 'menu-builder', component: MenuBuilderView },
        { path: 'id-resolver', name: 'id-resolver', component: IdResolverView },
        { path: 'groups', name: 'groups', component: GroupsView },
        { path: 'bots', name: 'bots', component: BotsView },
        { path: 'notifications', name: 'notifications', component: NotificationsView },
        { path: 'control', name: 'control', component: ControlPanelView },
        { path: 'control-panel', name: 'control-panel', component: ControlPanelView },
        { path: 'settings', name: 'settings', component: SettingsView },
        { path: 'health', name: 'health', component: HealthView },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isAuthenticated) {
    return '/login'
  }
  if (to.path === '/login' && auth.isAuthenticated) {
    return '/'
  }
  return true
})

export default router
