# План автоматической регистрации Opus и получения auth-токенов

## Цель
Автоматически регистрировать аккаунты Opus и получать Bearer-токены при исчерпании лимитов trial, используя ротацию email (Gmail/Yandex) и динамические прокси.

---

## Защиты Opus (из документации)

| Защита | Эндпоинт/Механизм | Обход |
|--------|-------------------|------|
| **IP Risk** | `GET /api/client-access-control?q=ipRisk` | Residential/mobile прокси (не datacenter) |
| **Multi-account** | `POST /api/login-users/check-multi-accounts` | Новый IP на каждую регистрацию |
| **Временные email** | Чёрный список доменов | Только Gmail/Yandex (реальные домены) |
| **PKCE** | codeVerifier в sessionStorage | Полный browser flow через Playwright |

---

## Архитектура решения

### Вариант A: Playwright + Gmail API (рекомендуемый)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Gmail/Yandex   │     │   Playwright     │     │  Opus API       │
│  (получение     │◄────│   (полный flow   │────►│  (регистрация,  │
│   кода из       │     │   логина)        │     │   login-profiles)│
│   письма)       │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                         │
         │                         │  Residential proxy
         │                         ▼
         │                ┌──────────────────┐
         └───────────────►│  clip.opus.pro   │
                          │  (PKCE, cookies) │
                          └──────────────────┘
```

**Почему Playwright обязателен:**
- `codeVerifier` генерируется **только в браузере** при клике на "Login"
- Хранится в `sessionStorage` — недоступен из чистых HTTP-запросов
- Без полного browser flow PKCE не пройти

### Вариант B: Гибрид (частичная автоматизация)

Если Playwright слишком тяжёлый:
1. **Вручную** один раз пройти flow в браузере с прокси
2. Сохранить `codeVerifier` из sessionStorage
3. Автоматически: запрос кода на email → получение кода через Gmail API → `GET login-profiles?code=X&codeVerifier=Y`

**Минус:** codeVerifier привязан к одной сессии; при новом логине нужен новый.

---

## Пошаговый flow (Playwright)

### 1. Подготовка
- **Email:** Gmail с App Password или Yandex с OAuth (Gmail API / IMAP для чтения писем)
- **Прокси:** Residential (Bright Data, Oxylabs, Smartproxy) — **не** datacenter
- **Playwright** с `chromium` или `firefox`

### 2. Регистрация (первый визит)

```
1. Запуск браузера с proxy
2. context.addInitScript() — установить deviceId в localStorage ("_opedid")
3. Переход на https://clip.opus.pro
4. Клик "Sign in" → "Email"
5. Ввод email (gmail.com / yandex.ru)
6. Клик "Send code"
   → codeVerifier сохраняется в sessionStorage["code-verifier"]
   → редирект на страницу ввода кода ИЛИ остаёмся на той же
7. Ожидание письма (Gmail API / IMAP polling)
8. Извлечение 6-значного кода из письма
9. Ввод кода в форму
10. После успеха — извлечь tokens из ответа / cookies / localStorage
```

### 3. Извлечение токена

После успешного логина токен может быть в:
- `localStorage` (WorkOS/Auth0)
- Cookies
- Ответе `authenticate` (если вызывается через их API)

Нужно проверить в DevTools после ручного логина.

### 4. Сохранение учётных данных

```json
{
  "email": "user@gmail.com",
  "bearer_token": "eyJ...",
  "org_id": "org_xxx",
  "user_id": "user_xxx",
  "created_at": "2026-02-16T...",
  "proxy_used": "residential:..."
}
```

---

## Email: Gmail vs Yandex

### Gmail
- **Gmail API** — читать inbox, искать письма от Opus
- Требует OAuth или Service Account
- Домены `gmail.com`, `googlemail.com` — обычно не в чёрном списке

### Yandex
- **IMAP** или **Yandex API**
- Домены `yandex.ru`, `yandex.com` — тоже «белые»
- Можно создавать поддомены `username@yandex.ru`

### Ротация
- Пулы: `user1@gmail.com`, `user2@gmail.com`, … или микс Gmail + Yandex
- Один email = один trial
- После исчерпания trial — переключаться на следующий аккаунт из пула

---

## Заголовки API (из login_opus.js)

| Header | Генерация |
|--------|-----------|
| `X-OPUS-DID` | `$device_{hash(userAgent+screen+lang)}_{random}` или `$device_{timestamp}_{random}` |
| `X-OPUS-CRID` | Случайная строка 5 символов (per-request) |
| `X-OPUS-LANG` | `en` или `ru` |
| `X-OPUS-UTM` | `{"source":"..."}` |
| `intl` | base64(`{"locale":"ru","timeZone":"Europe/Moscow"}`) |

Для **неавторизованных** запросов (login-codes, login-profiles) — без Bearer.

---

## Риски и ограничения

1. **Обновление защит** — Opus может добавить fingerprinting, CAPTCHA, rate limits
2. **Репутация прокси** — дешёвые residential могут быть в базах риска
3. **ToS** — автоматическая регистрация может нарушать условия использования
4. **Rate limit** — не создавать много аккаунтов с одного IP/прокси-пула

---

## Минимальный прототип (Python)

```python
# Псевдокод
async def register_opus_account(email: str, proxy: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            proxy={"server": proxy},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
        )
        page = await context.new_page()
        
        # 1. Установить deviceId
        await page.add_init_script("""
            localStorage.setItem('_opedid', '$device_' + Date.now() + '_' + Math.random().toString(36).slice(2,15));
        """)
        
        # 2. Перейти и инициировать логин
        await page.goto("https://clip.opus.pro")
        await page.click("text=Sign in")  # селектор уточнить
        await page.click("text=Email")
        await page.fill("input[type=email]", email)
        await page.click("button:has-text('Send')")
        
        # 3. Дождаться письма, получить код
        code = await wait_for_opus_code(email)  # Gmail API / IMAP
        
        # 4. Ввести код
        await page.fill("input[placeholder*='code']", code)
        await page.click("button:has-text('Verify')")
        
        # 5. Извлечь токен
        # Варианты: page.evaluate для localStorage, или перехват network
        token = await page.evaluate("""() => {
            // Найти в localStorage / cookies
            return localStorage.getItem('workos_session') || document.cookie;
        }""")
        
        return {"email": email, "token": token, ...}
```

---

## Чеклист перед реализацией

- [ ] Проверить, что Gmail/Yandex не в чёрном списке (тест регистрации)
- [ ] Выбрать провайдера residential-прокси
- [ ] Реализовать получение кода из Gmail (API или IMAP)
- [ ] Уточнить селекторы на clip.opus.pro (могут меняться)
- [ ] Определить, где хранится Bearer после логина
- [ ] Добавить ротацию аккаунтов в main.py при 401/403
