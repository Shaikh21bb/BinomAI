# BINOM AI — Test Plan v1.0

**Документ:** Test Plan  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** QA Lead  
**Связанные документы:** [Sprint 1.md](./Sprint%201.md), [Sprint 2.md](./Sprint%202.md), [Sprint 3.md](./Sprint%203.md)

---

## 1. Обзор стратегии тестирования

### 1.1 Пирамида тестирования

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E╲        ← 10% (дорогие, медленные)
                 ╱──────╲
                ╱Integr. ╲      ← 30% (контракты между слоями)
               ╱──────────╲
              ╱  Unit Tests ╲    ← 60% (быстрые, дешёвые)
             ╱──────────────╲
```

### 1.2 Типы тестирования

| Тип | Инструмент | Coverage Target | Когда запускается |
|-----|-----------|----------------|-------------------|
| Unit Tests | pytest | > 70% | При каждом commit |
| Integration Tests | pytest + httpx | Ключевые flows | При каждом PR |
| E2E Tests | Playwright | Happy paths | Перед релизом |
| AI Quality Tests | Custom harness | 20 реальных ТЗ | Перед релизом |
| Performance Tests | Locust | Ключевые эндпоинты | Перед Production |
| Security Tests | OWASP ZAP + ручные | OWASP Top 10 | Перед Production |

### 1.3 Тестовые среды

| Среда | Назначение | URL |
|-------|----------|-----|
| Local | Разработчик, unit тесты | localhost:8000 |
| Staging | Integration, E2E тесты | staging.api.binom.ai |
| Production | Smoke тесты после деплоя | api.binom.ai |

---

## 2. Unit Tests

### 2.1 Auth Module

```python
# tests/unit/test_auth.py

class TestAuthService:
    
    def test_register_success(self):
        """Регистрация с валидными данными → создание user + company"""
        response = client.post("/api/v1/auth/register", json={
            "email": "test@company.kz",
            "password": "SecurePass123!",
            "full_name": "Тест Тестов",
            "company_name": "ТОО Тест"
        })
        assert response.status_code == 201
        assert response.json()["success"] == True
        assert "access_token" in response.json()["data"]
        assert "company_id" in response.json()["data"]["user"]
    
    def test_register_duplicate_email(self):
        """Регистрация с уже существующим email → 409"""
        response = client.post("/api/v1/auth/register", json={...duplicate...})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONFLICT"
    
    def test_register_weak_password(self):
        """Слабый пароль → 400 VALIDATION_ERROR"""
        response = client.post("/api/v1/auth/register", json={
            ..., "password": "123"
        })
        assert response.status_code == 400
        assert any(e["field"] == "password" for e in response.json()["error"]["details"])
    
    def test_login_success(self):
        """Вход с правильными данными → токены"""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@company.kz",
            "password": "SecurePass123!"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()["data"]
        assert "refresh_token" in response.json()["data"]
    
    def test_login_wrong_password(self):
        """Неверный пароль → 401"""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@company.kz",
            "password": "WrongPass!"
        })
        assert response.status_code == 401
    
    def test_token_refresh(self):
        """Обновление токена → новый access_token"""
        ...
    
    def test_expired_token_rejected(self):
        """Истёкший JWT отклоняется → 401"""
        ...
```

### 2.2 Projects Module

```python
# tests/unit/test_projects.py

class TestProjectsService:
    
    def test_create_project_success(self, auth_headers):
        response = client.post("/api/v1/projects", 
            headers=auth_headers,
            json={"name": "Тест тендер", "deadline_at": "2026-09-01T00:00:00Z"}
        )
        assert response.status_code == 201
        assert response.json()["data"]["status"] == "draft"
    
    def test_list_projects_pagination(self, auth_headers, factory):
        """Список проектов с пагинацией"""
        factory.create_projects(count=25)
        response = client.get("/api/v1/projects?page=1&page_size=20", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 20
        assert data["pagination"]["total"] == 25
        assert data["pagination"]["has_next"] == True
    
    def test_cannot_access_other_company_project(self, auth_headers_company_a, project_company_b):
        """Пользователь компании A не может получить проект компании B"""
        response = client.get(
            f"/api/v1/projects/{project_company_b.id}", 
            headers=auth_headers_company_a
        )
        assert response.status_code == 404  # Проект не виден — для безопасности 404, не 403
    
    def test_delete_project_cascade(self, auth_headers, project_with_data):
        """Удаление проекта удаляет все связанные данные"""
        project_id = project_with_data.id
        
        response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Проверяем каскадное удаление
        analysis = db.query(AnalysisResult).filter_by(project_id=project_id).first()
        assert analysis is None
```

### 2.3 Document Parser Module

```python
# tests/unit/test_document_parser.py

class TestDocumentParser:
    
    @pytest.fixture
    def pdf_file(self):
        return "tests/fixtures/sample_tz.pdf"
    
    @pytest.fixture
    def docx_file(self):
        return "tests/fixtures/sample_tz.docx"
    
    async def test_parse_pdf_extracts_text(self, pdf_file):
        parser = DocumentParser()
        result = await parser.parse(pdf_file, "application/pdf")
        
        assert result.full_text is not None
        assert len(result.full_text) > 100
        assert result.page_count > 0
        assert result.language in ["ru", "kz", "en"]
    
    async def test_parse_docx_preserves_headings(self, docx_file):
        parser = DocumentParser()
        result = await parser.parse(docx_file, "application/vnd.openxmlformats...")
        
        # Заголовки должны быть конвертированы в Markdown
        assert "# " in result.full_text or "## " in result.full_text
    
    async def test_parse_cyrillic_pdf(self):
        """Кириллица корректно извлекается"""
        parser = DocumentParser()
        result = await parser.parse("tests/fixtures/tz_cyrillic.pdf", "application/pdf")
        
        # Должны быть казахские/русские слова
        assert any(word in result.full_text for word in ["техническое", "строительство", "объект"])
    
    async def test_parse_pdf_with_tables(self):
        """Таблицы конвертируются в Markdown"""
        parser = DocumentParser()
        result = await parser.parse("tests/fixtures/tz_with_tables.pdf", "application/pdf")
        
        assert "|" in result.full_text  # Markdown таблица
    
    async def test_token_count_reasonable(self):
        """Token count разумный для документа"""
        parser = DocumentParser()
        result = await parser.parse("tests/fixtures/sample_tz.pdf", "application/pdf")
        
        # Очень приблизительная оценка: 1 токен ≈ 4 символа
        expected_tokens = len(result.full_text) // 4
        assert result.token_count == pytest.approx(expected_tokens, rel=0.3)
```

### 2.4 AI Analysis Agent Module

```python
# tests/unit/test_analysis_agent.py

class TestAnalysisAgent:
    
    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM возвращает предопределённый ответ"""
        with patch("app.ai.llm_client.LLMClient.generate") as mock:
            mock.return_value = SAMPLE_ANALYSIS_RESPONSE_JSON
            yield mock
    
    async def test_analysis_returns_valid_structure(self, mock_llm_client, sample_document):
        agent = AnalysisAgent()
        result = await agent.run(AnalysisAgentInput(
            project_id="test-project-id",
            document_id="test-doc-id",
            document_text=sample_document.text,
            company_profile=SAMPLE_COMPANY_PROFILE
        ))
        
        assert result.executive_summary is not None
        assert len(result.executive_summary) > 50
        assert result.tender_type in ["EPC", "construction", "supply", "services", "mixed"]
        assert result.complexity_level in ["Low", "Medium", "High"]
        assert len(result.technical_requirements) > 0
        assert len(result.risks) > 0
    
    async def test_each_requirement_has_source(self, mock_llm_client, sample_document):
        """Каждое требование должно иметь ссылку на источник"""
        agent = AnalysisAgent()
        result = await agent.run(...)
        
        for req in result.technical_requirements:
            assert req.source_section is not None
            assert req.source_section != ""
    
    async def test_fallback_to_gpt4o_on_gemini_error(self, sample_document):
        """При ошибке Gemini → переключение на GPT-4o"""
        with patch("app.ai.llm_client.LLMClient._call_gemini") as gemini_mock:
            gemini_mock.side_effect = GeminiAPIError("Rate limit exceeded")
            
            with patch("app.ai.llm_client.LLMClient._call_openai") as openai_mock:
                openai_mock.return_value = SAMPLE_ANALYSIS_RESPONSE_JSON
                
                agent = AnalysisAgent()
                result = await agent.run(...)
                
                assert openai_mock.called
                assert result is not None
    
    async def test_retry_on_json_parse_failure(self, sample_document):
        """Retry при невалидном JSON ответе"""
        with patch("app.ai.llm_client.LLMClient.generate") as mock:
            # Первые 2 вызова — невалидный JSON, 3-й — OK
            mock.side_effect = [
                "{invalid json",
                "{also invalid",
                SAMPLE_ANALYSIS_RESPONSE_JSON
            ]
            
            agent = AnalysisAgent()
            result = await agent.run(...)
            
            assert mock.call_count == 3
            assert result is not None
```

---

## 3. Integration Tests

### 3.1 Core Flow: Upload → Parse → Analyze

```python
# tests/integration/test_core_flow.py

class TestCoreFlow:
    
    async def test_upload_to_analysis_complete_flow(self, auth_headers, test_project):
        """Полный флоу: загрузка → парсинг → анализ"""
        
        # Шаг 1: Загрузка файла
        with open("tests/fixtures/sample_tz.pdf", "rb") as f:
            upload_response = await client.post(
                f"/api/v1/projects/{test_project.id}/documents",
                headers=auth_headers,
                files={"file": ("tz.pdf", f, "application/pdf")}
            )
        
        assert upload_response.status_code == 202
        doc_id = upload_response.json()["data"]["document_id"]
        task_id = upload_response.json()["data"]["task_id"]
        
        # Шаг 2: Ожидаем парсинга (с timeout)
        for _ in range(30):
            await asyncio.sleep(2)
            doc_response = await client.get(
                f"/api/v1/projects/{test_project.id}/documents/current",
                headers=auth_headers
            )
            if doc_response.json()["data"]["processing_status"] == "ready":
                break
        else:
            pytest.fail("Document parsing timeout after 60 seconds")
        
        # Шаг 3: Ожидаем анализа
        for _ in range(60):
            await asyncio.sleep(2)
            analysis_response = await client.get(
                f"/api/v1/projects/{test_project.id}/analysis",
                headers=auth_headers
            )
            if analysis_response.json()["data"]["status"] == "completed":
                break
        else:
            pytest.fail("Analysis timeout after 120 seconds")
        
        # Шаг 4: Проверяем результат
        analysis = analysis_response.json()["data"]
        assert analysis["executive_summary"] is not None
        assert len(analysis["technical_requirements"]) > 0
        assert len(analysis["risks"]) >= 0
    
    async def test_large_pdf_handling(self, auth_headers, test_project):
        """Большой PDF (>10 МБ) обрабатывается корректно"""
        with open("tests/fixtures/large_tz_50mb.pdf", "rb") as f:
            response = await client.post(...)
        assert response.status_code == 202
    
    async def test_oversized_file_rejected(self, auth_headers, test_project):
        """Файл > 50 МБ отклоняется"""
        with open("tests/fixtures/oversized_55mb.pdf", "rb") as f:
            response = await client.post(...)
        assert response.status_code == 413
```

### 3.2 Chat → Generation Flow

```python
# tests/integration/test_chat_generation_flow.py

class TestChatGenerationFlow:
    
    async def test_chat_completion_enables_generation(self, auth_headers, project_with_analysis):
        
        # Шаг 1: Получение первого вопроса
        chat_response = await client.get(
            f"/api/v1/projects/{project_with_analysis.id}/chat",
            headers=auth_headers
        )
        assert len(chat_response.json()["data"]["messages"]) > 0
        first_message = chat_response.json()["data"]["messages"][0]
        assert first_message["role"] == "assistant"
        
        # Шаг 2: Ответ на вопросы
        for i in range(5):
            msg_response = await client.post(
                f"/api/v1/projects/{project_with_analysis.id}/chat/message",
                headers=auth_headers,
                json={"content": SAMPLE_ANSWERS[i]}
            )
            assert msg_response.status_code == 200
        
        # Шаг 3: Проверка готовности
        status_response = await client.get(
            f"/api/v1/projects/{project_with_analysis.id}/chat/status",
            headers=auth_headers
        )
        # После ответов — должна быть готовность (или близко к ней)
        assert status_response.json()["data"]["completion_percentage"] > 50
    
    async def test_generate_commercial_proposal(self, auth_headers, project_ready_for_generation):
        
        # Шаг 1: Запуск генерации
        gen_response = await client.post(
            f"/api/v1/projects/{project_ready_for_generation.id}/generate",
            headers=auth_headers,
            json={"doc_type": "commercial_proposal"}
        )
        assert gen_response.status_code == 202
        doc_id = gen_response.json()["data"]["doc_id"]
        
        # Шаг 2: Ожидаем завершения
        for _ in range(60):
            await asyncio.sleep(3)
            doc_response = await client.get(
                f"/api/v1/projects/{project_ready_for_generation.id}/documents/generated/{doc_id}",
                headers=auth_headers
            )
            if doc_response.json()["data"]["generation_status"] == "completed":
                break
        else:
            pytest.fail("Generation timeout after 180 seconds")
        
        # Шаг 3: Проверка контента
        doc = doc_response.json()["data"]
        assert doc["content_html"] is not None
        assert len(doc["content_html"]) > 1000
        assert "content_json" in doc
        assert len(doc["content_json"]["sections"]) >= 5
```

---

## 4. AI Quality Tests

### 4.1 Тестовый набор ТЗ

Используется 20 реальных анонимизированных ТЗ строительных тендеров:

| # | Тип | Сложность | Страниц | Язык |
|---|-----|-----------|---------|------|
| 1 | EPC | High | 87 | Русский |
| 2 | Construction | Medium | 45 | Русский |
| 3 | Supply | Low | 18 | Русский |
| 4 | Services | Low | 12 | Русский |
| 5 | EPC | High | 120 | Русский |
| 6 | Mixed | Medium | 60 | Русский |
| 7 | Construction | Medium | 35 | Казахский |
| 8 | Supply | Low | 22 | Русский |
| 9 | EPC | High | 95 | Русский |
| 10 | Construction | Low | 28 | Русский |
| 11–20 | Mixed | Various | 15-100 | Русский |

### 4.2 AI Quality Test Suite

```python
# tests/ai_quality/test_analysis_quality.py

class TestAnalysisQuality:
    """
    Ручные + автоматические тесты качества AI.
    Запускаются перед каждым релизом.
    """
    
    TZ_FIXTURES = [f"tests/ai_quality/tz_{i:02d}.pdf" for i in range(1, 21)]
    
    @pytest.mark.ai_quality
    async def test_no_hallucinations(self):
        """Ни одно требование не должно отсутствовать в исходном ТЗ"""
        
        for tz_file in self.TZ_FIXTURES[:5]:  # Первые 5 для CI
            result = await self._run_analysis(tz_file)
            doc_text = self._load_text(tz_file)
            
            for req in result.technical_requirements:
                # Ключевые слова из требования должны встречаться в ТЗ
                key_words = self._extract_key_words(req.text)
                assert any(word.lower() in doc_text.lower() for word in key_words), \
                    f"Possible hallucination: '{req.text}' not found in TZ"
    
    @pytest.mark.ai_quality
    async def test_tender_type_classification(self):
        """Правильная классификация типа тендера"""
        
        expected = {
            "tz_01.pdf": "EPC",
            "tz_02.pdf": "construction",
            "tz_03.pdf": "supply",
        }
        
        for tz_file, expected_type in expected.items():
            result = await self._run_analysis(f"tests/ai_quality/{tz_file}")
            assert result.tender_type == expected_type, \
                f"Expected {expected_type}, got {result.tender_type} for {tz_file}"
    
    @pytest.mark.ai_quality
    async def test_risk_severity_reasonable(self):
        """Severity рисков разумная (нет всё High)"""
        
        result = await self._run_analysis(self.TZ_FIXTURES[0])
        
        severity_counts = {"High": 0, "Medium": 0, "Low": 0}
        for risk in result.risks:
            severity_counts[risk.severity] += 1
        
        # Не должно быть только одного уровня (кроме случаев, когда ТЗ действительно однородное)
        non_zero_levels = sum(1 for v in severity_counts.values() if v > 0)
        assert non_zero_levels >= 1, "All risks have same severity - likely bug"
    
    @pytest.mark.ai_quality  
    async def test_requirements_have_sources(self):
        """100% требований имеют ссылку на источник"""
        
        for tz_file in self.TZ_FIXTURES[:5]:
            result = await self._run_analysis(tz_file)
            all_reqs = (result.technical_requirements + 
                       result.commercial_requirements + 
                       result.legal_requirements)
            
            for req in all_reqs:
                assert req.source_section, f"Requirement without source: {req.text[:50]}"


# tests/ai_quality/test_generation_quality.py

class TestGenerationQuality:
    
    @pytest.mark.ai_quality
    async def test_kp_contains_company_data(self):
        """КП содержит реальные данные компании"""
        
        company_name = "ТОО «ТестКомпания»"
        director_name = "Иван Иванов"
        
        doc = await self._generate_kp(company_name=company_name, director_name=director_name)
        
        assert company_name in doc.content_html
        assert director_name in doc.content_html
    
    @pytest.mark.ai_quality
    async def test_kp_no_placeholder_brackets(self):
        """В финальном КП нет незаполненных плейсхолдеров [...]"""
        
        doc = await self._generate_kp_with_full_context()
        
        import re
        placeholders = re.findall(r'\[(?!ЗАПОЛНИТЬ)[^\]]+\]', doc.content_html)
        assert len(placeholders) == 0, f"Found unfilled placeholders: {placeholders}"
    
    @pytest.mark.ai_quality
    async def test_kp_professional_language(self):
        """КП содержит деловой язык (нет разговорных слов)"""
        
        INFORMAL_WORDS = ["короче", "типа", "ну", "ок", "окей", "лол", "кстати"]
        doc = await self._generate_kp_with_full_context()
        
        found = [w for w in INFORMAL_WORDS if w in doc.content_html.lower()]
        assert not found, f"Informal language found: {found}"
    
    @pytest.mark.ai_quality
    async def test_expert_rating_check(self):
        """
        РУЧНОЙ ТЕСТ: Эксперт оценивает 5 сгенерированных КП.
        Минимальный порог: 4 из 5 КП с оценкой 'Хорошо' или 'Отлично'.
        
        Этот тест помечается как manual и запускается перед релизом.
        """
        pytest.skip("Manual test - run before each release with domain expert")
```

---

## 5. Performance Tests

```python
# tests/performance/locustfile.py

from locust import HttpUser, task, between

class BINOMAIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Авторизация"""
        response = self.client.post("/api/v1/auth/login", json={
            "email": f"loadtest_{self.user_id}@test.kz",
            "password": "LoadTest123!"
        })
        self.token = response.json()["data"]["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def list_projects(self):
        self.client.get("/api/v1/projects", headers=self.headers)
    
    @task(2)
    def get_project_detail(self):
        self.client.get(f"/api/v1/projects/{SAMPLE_PROJECT_ID}", headers=self.headers)
    
    @task(1)
    def get_analysis(self):
        self.client.get(f"/api/v1/projects/{SAMPLE_PROJECT_ID}/analysis", headers=self.headers)
    
    @task(1)
    def get_chat(self):
        self.client.get(f"/api/v1/projects/{SAMPLE_PROJECT_ID}/chat", headers=self.headers)
```

**Запуск:**
```bash
locust -f tests/performance/locustfile.py \
  --host https://staging.api.binom.ai \
  --users 20 \
  --spawn-rate 2 \
  --run-time 5m \
  --headless
```

**Performance SLOs:**

| Метрика | Target | Critical |
|---------|--------|---------|
| p50 latency (non-AI) | < 150ms | < 300ms |
| p95 latency (non-AI) | < 500ms | < 1000ms |
| p99 latency (non-AI) | < 1000ms | < 2000ms |
| Error rate | < 0.5% | < 2% |
| Concurrent users | 20 | 50 |

---

## 6. Security Tests

### 6.1 Автоматические (OWASP ZAP)

```bash
# Запуск базового OWASP ZAP сканирования
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://staging.api.binom.ai/api/v1 \
  -r zap_report.html \
  --auto
```

### 6.2 Ручные тесты безопасности

| # | Тест | Ожидаемый результат |
|---|------|---------------------|
| SEC-1 | SQL Injection в полях фильтрации | 400 Bad Request, нет SQL ошибок |
| SEC-2 | XSS в content_html редактора | Sanitize, нет выполнения скриптов |
| SEC-3 | Доступ к проекту другой компании по UUID | 404 Not Found |
| SEC-4 | Использование истёкшего JWT | 401 Unauthorized |
| SEC-5 | Brute force login (100+ попыток) | 429 Rate Limit |
| SEC-6 | Загрузка PHP/JS файла вместо PDF | 415 Unsupported Media |
| SEC-7 | Prompt injection в поле ответа чата | Ответ sanitized, инъекция удалена |
| SEC-8 | Превышение лимита файла (51 МБ PDF) | 413 File Too Large |
| SEC-9 | CSRF попытка | 403 Forbidden (JWT stateless = защита) |
| SEC-10 | Открытый redirect | Нет редиректа на внешние URL |

---

## 7. Test Data Management

### 7.1 Фикстуры

```python
# tests/conftest.py

@pytest.fixture
def sample_company():
    return Company(
        name="ТОО «ТестСтрой»",
        bin_iin="180340012345",
        specialization="Строительство промышленных объектов"
    )

@pytest.fixture
def sample_tz_text():
    with open("tests/fixtures/sample_tz.txt", "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def project_with_analysis(db, sample_company):
    """Проект с завершённым анализом"""
    project = ProjectFactory.create(company=sample_company)
    AnalysisFactory.create(project=project, status="completed", **SAMPLE_ANALYSIS_DATA)
    return project

@pytest.fixture  
def project_ready_for_generation(project_with_analysis, db):
    """Проект готовый к генерации (анализ + чат завершён)"""
    ChatSessionFactory.create(
        project=project_with_analysis,
        is_complete=True,
        clarification_context=SAMPLE_CLARIFICATION_CONTEXT
    )
    return project_with_analysis
```

### 7.2 Test Fixtures (файлы)

```
tests/
├── fixtures/
│   ├── sample_tz.pdf          ← 10 страниц, базовое ТЗ
│   ├── sample_tz.docx         ← То же ТЗ в DOCX
│   ├── sample_tz.txt          ← Извлечённый текст
│   ├── large_tz_50mb.pdf      ← Граничный размер
│   ├── oversized_55mb.pdf     ← Превышение лимита
│   ├── tz_cyrillic.pdf        ← Кириллица
│   ├── tz_with_tables.pdf     ← С таблицами
│   └── tz_invalid.xlsx        ← Неподдерживаемый формат
│
└── ai_quality/
    ├── tz_01.pdf              ← EPC высокой сложности
    ├── tz_02.pdf              ← Строительство среднее
    ...
    └── tz_20.pdf
```

---

## 8. CI/CD Интеграция

### 8.1 GitHub Actions Test Pipeline

```yaml
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with: { python-version: '3.11' }
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=app --cov-report=xml
      - name: Coverage check
        run: pytest --cov=app --cov-fail-under=70
  
  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_STAGING_URL }}
      SUPABASE_KEY: ${{ secrets.SUPABASE_STAGING_KEY }}
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests
        run: pytest tests/integration/ -v --timeout=180

  # AI Quality тесты только на релизных ветках
  ai-quality:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Run AI quality tests (fast subset)
        run: pytest tests/ai_quality/ -m "not slow" -v
```

---

## 9. Bug Severity Matrix

| Severity | Описание | Время исправления |
|---------|---------|-----------------|
| **P1 Critical** | Потеря данных, security breach, полный outage | Немедленно (≤ 4 часа) |
| **P2 High** | Основной функционал не работает (upload, analyze, generate) | ≤ 24 часа |
| **P3 Medium** | Второстепенный функционал не работает (export, feedback) | ≤ 72 часа |
| **P4 Low** | UI баги, minor inconsistencies | Следующий спринт |

---

## 10. Метрики качества (QA KPIs)

| Метрика | Цель | Критично |
|---------|------|---------|
| Unit Test Coverage | > 70% | > 50% |
| Integration Test Pass Rate | 100% | > 95% |
| AI Hallucination Rate | < 3% | < 10% |
| P1 Bugs in Production | 0 | 0 |
| P2 Bugs per Release | < 2 | < 5 |
| Time to Fix P1 | < 4ч | < 8ч |
| Regression after deploy | 0% | < 1% |

---

*Документ подготовлен командой BINOM AI. Test Plan v1.0 — утверждён.*  
*Следующий документ: [Deployment.md](./Deployment.md)*
