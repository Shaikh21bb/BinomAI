import { AppShell } from '@/components/AppShell';
import { ProjectsDashboard } from '@/components/ProjectsDashboard';

export default function TendersPage() {
  return (
    <AppShell>
      <ProjectsDashboard
        pageLabel="Активные тендеры"
        pageDescription="Управление и контроль вашего тендерного портфеля."
      />
    </AppShell>
  );
}
