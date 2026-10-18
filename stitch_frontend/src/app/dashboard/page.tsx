import { AppShell } from '@/components/AppShell';
import { ProjectsDashboard } from '@/components/ProjectsDashboard';

export default function DashboardPage() {
  return (
    <AppShell>
      <ProjectsDashboard
        pageLabel="Рабочий стол"
        pageDescription="Управляйте тендерами, проверяйте товары и держите ближайшие сроки в фокусе."
      />
    </AppShell>
  );
}
