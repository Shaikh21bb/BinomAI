import { AppShell } from '@/components/AppShell';
import { ProjectsDashboard } from '@/components/ProjectsDashboard';

export default function DashboardPage() {
  return (
    <AppShell>
      <ProjectsDashboard
        pageLabel="Активные тендеры"
        pageDescription="Мониторинг текущих процедур и автоматизированный ИИ-анализ."
      />
    </AppShell>
  );
}
