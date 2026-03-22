import os
required_files=[
'dashboard-vue/src/views/LoginView.vue','dashboard-vue/src/views/dashboard/DashboardLayout.vue','dashboard-vue/src/views/dashboard/HomeView.vue','dashboard-vue/src/views/dashboard/OpportunitiesView.vue','dashboard-vue/src/views/dashboard/UsersView.vue','dashboard-vue/src/views/dashboard/UserProfileView.vue','dashboard-vue/src/views/dashboard/SupportView.vue','dashboard-vue/src/views/dashboard/SupportTeamView.vue','dashboard-vue/src/views/dashboard/StoresView.vue','dashboard-vue/src/views/dashboard/StoreRequestsView.vue','dashboard-vue/src/views/dashboard/HealthView.vue','dashboard-vue/src/views/dashboard/SettingsView.vue','dashboard-vue/src/views/dashboard/NotificationsView.vue','dashboard-vue/src/views/dashboard/MenuBuilderView.vue','dashboard-vue/src/views/dashboard/GroupsView.vue','dashboard-vue/src/views/dashboard/IdResolverView.vue','dashboard-vue/src/views/dashboard/BotsView.vue',
'dashboard-vue/src/components/layout/Sidebar.vue','dashboard-vue/src/components/layout/TopBar.vue','dashboard-vue/src/components/layout/NotificationBell.vue','dashboard-vue/src/components/layout/PageHeader.vue','dashboard-vue/src/components/ui/BaseSelect.vue','dashboard-vue/src/components/ui/BaseModal.vue','dashboard-vue/src/components/ui/LoadingSpinner.vue','dashboard-vue/src/components/ui/EmptyState.vue','dashboard-vue/src/components/telegram/TelegramResolver.vue',
'dashboard-vue/src/stores/auth.js','dashboard-vue/src/stores/notifications.js','dashboard-vue/src/stores/users.js','dashboard-vue/src/stores/opportunities.js',
'dashboard-vue/src/api/axios.js','dashboard-vue/src/api/auth.js','dashboard-vue/src/api/settings.js','dashboard-vue/src/api/support.js',
'dashboard-vue/src/directives/tooltip.js','dashboard-vue/src/utils/format.js']
missing=[]
for f in required_files:
    if os.path.exists(f):
        print(f'OK {f}')
    else:
        print(f'MISS {f}')
        missing.append(f)
print(f'\\nTotal: {len(required_files)} files')
print(f'Missing: {len(missing)}')
