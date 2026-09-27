'use client';

interface GlobalErrorProps {
  error: Error & { digest?: string };
  retry: () => void;
}

const styles = `
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #f8faff; color: #101418; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
  .global-error-shell { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
  .global-error-card { width: min(100%, 560px); padding: 40px; border: 1px solid #dfe4f0; border-radius: 12px; background: #fff; text-align: center; box-shadow: 0 12px 40px rgba(30, 48, 80, .08); }
  .global-error-mark { width: 56px; height: 56px; margin: 0 auto 20px; border-radius: 14px; display: grid; place-items: center; background: #101418; color: #fff; font-size: 24px; font-weight: 800; }
  .global-error-kicker { margin: 0 0 8px; color: #d70015; font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
  .global-error-title { margin: 0; font-size: clamp(24px, 5vw, 34px); line-height: 1.15; }
  .global-error-copy { margin: 14px auto 0; max-width: 430px; color: #5b6472; line-height: 1.6; }
  .global-error-code { margin: 12px 0 0; color: #5b6472; font-size: 12px; }
  .global-error-button { margin-top: 28px; border: 0; border-radius: 8px; background: #101418; color: #fff; cursor: pointer; font: inherit; font-weight: 700; padding: 12px 22px; }
  .global-error-button:hover { opacity: .88; }
  .global-error-button:focus-visible { outline: 3px solid #8ab4ff; outline-offset: 3px; }
  @media (prefers-color-scheme: dark) {
    body { background: #0a0e1a; color: #e2e6f0; }
    .global-error-card { border-color: #262e42; background: #0e1424; box-shadow: none; }
    .global-error-mark, .global-error-button { background: #e2e6f0; color: #101418; }
    .global-error-copy, .global-error-code { color: #b8c0d0; }
  }
`;

export default function GlobalError({ error, retry }: GlobalErrorProps) {
  return (
    <html lang="ru">
      <head>
        <title>Ошибка — BINOM AI</title>
        <style>{styles}</style>
      </head>
      <body>
        <main className="global-error-shell">
          <section className="global-error-card" aria-labelledby="global-error-title">
            <div className="global-error-mark" aria-hidden="true">B</div>
            <p className="global-error-kicker">Системная ошибка</p>
            <h1 id="global-error-title" className="global-error-title">BINOM AI временно недоступен</h1>
            <p className="global-error-copy">
              Обновите приложение. Если ошибка повторится, сообщите администратору код обращения.
            </p>
            {error.digest ? <p className="global-error-code">Код обращения: {error.digest}</p> : null}
            <button type="button" className="global-error-button" onClick={retry}>Обновить приложение</button>
          </section>
        </main>
      </body>
    </html>
  );
}
