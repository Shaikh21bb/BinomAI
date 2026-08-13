import type { Metadata } from 'next';
import Landing from '@/components/Landing';

export const metadata: Metadata = {
  title: 'BINOM AI — AI-ассистент для участников закупок',
  description:
    'BINOM AI анализирует тендерную документацию, задаёт уточняющие вопросы и автоматически готовит коммерческие предложения, технические задания и сопроводительные письма на русском и казахском языках.',
};

export default function Home() {
  return <Landing />;
}
