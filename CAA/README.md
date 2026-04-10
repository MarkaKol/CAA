# CAA - CFM AntiFraud Analyzer

## Что это такое?

**CAA (CFM AntiFraud Analyzer)** — это профессиональный инструмент для реверс-инжиниринга антифрод-систем. Он позволяет увидеть, какие именно параметры вашего браузера проверяет антифрод (Protected Media, Cloudflare, Datadome и др.), и на основе этого анализа настроить обход.

## Проблема, которую решает CAA:

- Какие свойства браузера читает антифрод?
- Какие WebGL-параметры запрашиваются?
- Делает ли антифрод canvas-отпечаток?
- Отличается ли ваш CFM от чистого Chrome?
- На каком этапе происходит блокировка?

## Как это работает?


┌─────────────────────────────────────────────────────────────┐
│ CAA Workflow │
├─────────────────────────────────────────────────────────────┤
│ │
│ 1. CAA запускает CFM с инжектированным JS-сенсором │
│ ↓ │
│ 2. JS-ловушка перехватывает ВСЕ обращения антифрода: │
│ - navigator.webdriver, languages, plugins │
│ - canvas.toDataURL(), getImageData() │
│ - webgl.getParameter() │
│ - performance.now(), timing │
│ - все XHR/fetch/WebSocket запросы │
│ - добавление event listeners (mousemove, keydown и др.) │
│ ↓ │
│ 3. Логи отправляются в Python-анализатор │
│ ↓ │
│ 4. Анализатор сравнивает с базой триггеров │
│ ↓ │
│ 5. Вы получаете отчёт: │
│ - Оценка подозрительности (0-100) │
│ - Список обнаруженных триггеров │
│ - Сравнение с чистым Chrome │
│ - Рекомендации по исправлению │
│ ↓ │
│ 6. Вы идёте в код CFM и правите то, что выдаёт вас │
│ │
└─────────────────────────────────────────────────────────────┘



## Архитектура

CAA/
├── core/ # Ядро системы
│ ├── scanner_main.py # Оркестратор сканирования
│ ├── analyzer_core.py # Анализ и классификация триггеров
│ ├── cfm_adapter.py # Адаптер для вашего CFM
│ └── report_generator.py # Генерация отчётов (JSON/HTML)
│
├── js/ # JavaScript-ловушки
│ ├── trap_injected.js # Главный сенсор (Proxy на navigator, screen)
│ ├── canvas_trap.js # Перехват Canvas и WebGL
│ ├── network_trap.js # Перехват XHR, Fetch, WebSocket
│ └── behavior_trap.js # Мониторинг мыши, клавиатуры, скролла
│
├── config/ # Конфигурация
│ ├── settings.py # Настройки сканера и анализатора
│ └── triggers_db.json # База известных триггеров антифрода
│
├── profiles/ # Профили браузера
│ ├── clean_chrome.json # Чистый Chrome (эталон)
│ ├── cfm_default.json # Стандартный CFM
│ └── cfm_stealth.json # Усиленный стелс-режим
│
├── utils/ # Вспомогательные модули
│ ├── logger.py # Логирование
│ ├── network_utils.py # Анализ сетевых запросов
│ └── fingerprint_comparator.py # Сравнение отпечатков
│
├── scripts/ # Скрипты запуска
│ ├── run_scan.py # Одиночное сканирование
│ ├── batch_scan.py # Пакетное сканирование
│ └── compare_profiles.py # Сравнение профилей
│
└── tests/ # Тесты
├── test_trap.js # Тестирование JS-ловушки
└── test_analyzer.py # Юнит-тесты анализатора


## Что перехватывает JS-ловушка?

| Категория | Что перехватывается |
|-----------|---------------------|
| **Navigator** | webdriver, languages, plugins, userAgent, platform, hardwareConcurrency, deviceMemory |
| **Screen** | width, height, availWidth, availHeight, colorDepth, pixelDepth |
| **Canvas** | toDataURL(), getImageData(), fillText() |
| **WebGL** | getParameter(), getExtension() |
| **Performance** | now(), timing, navigation |
| **Network** | fetch(), XHR, sendBeacon, WebSocket |
| **Events** | addEventListener для mousemove, keydown, wheel, click |
| **Timing** | Время вызовов, stack traces |

## Система оценки подозрительности

| Уровень | Название | Вес | Примеры триггеров |
|---------|----------|-----|-------------------|
| 0 | Fingerprint | 15 | canvas, webgl, hardwareConcurrency |
| 1 | Environment | 25 | webdriver, languages, plugins |
| 2 | Behavior | 35 | отсутствие mousemove, keydown |
| 1 | Network | 20 | запросы на /collect, /fingerprint |
| 1 | Timing | 10 | performance.now(), navigation |

**Итоговая оценка:**
- 0-30: Низкая подозрительность (зелёный)
- 30-60: Средняя (жёлтый)
- 60-80: Высокая (оранжевый)
- 80-100: Критическая (красный)
