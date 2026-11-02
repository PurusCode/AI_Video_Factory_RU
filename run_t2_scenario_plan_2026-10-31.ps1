# AI Video Factory RU — T2: scenario-plan benchmark for three MWS deployments.
# Uses explicit UTF-8 byte handling for both request and response to avoid mojibake.
# The API key is read securely and is never written to benchmark files.

$ErrorActionPreference = 'Stop'

# Set the PowerShell console to UTF-8 as well. Files are saved explicitly below,
# so correct file encoding does not depend on the terminal code page.
try {
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [Console]::InputEncoding = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
    $OutputEncoding = $utf8NoBom
    & chcp.com 65001 | Out-Null
} catch {
    Write-Warning "Не удалось переключить кодовую страницу консоли. UTF-8 для файлов всё равно будет задан явно."
}

$project = 'project-alexsapan'
$baseUrl = "https://gpt.mwsapis.ru/projects/$project/openai/v1"
$outDir = Join-Path $PWD 'output\t2_scenario_plan_2026-10-31'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$deployments = @(
    [pscustomobject]@{ Name = 'gpt_oss_120b'; Id = 'video-farm-gpt-oss-120b-test'; InputRate = [decimal]13.42; OutputRate = [decimal]54.90 },
    [pscustomobject]@{ Name = 'gemma4_31b'; Id = 'video-farm-gemma-4-31b-test'; InputRate = [decimal]56.12; OutputRate = [decimal]224.48 },
    [pscustomobject]@{ Name = 'qwen36_35b'; Id = 'video-farm-qwen-36-35b-test'; InputRate = [decimal]70.76; OutputRate = [decimal]283.04 }
)

$prompt = @'
РОЛЬ
Ты — опытный сценарист и редактор образовательного видеоканала об искусственном интеллекте. Нужно разработать план одного объясняющего видео.

ТЕМА
«Что такое локальный ИИ и когда он полезен на обычном компьютере».

АУДИТОРИЯ И ПРОИЗВОДСТВО
- Русскоязычная аудитория, преимущественно новички, которым интересно практическое применение ИИ.
- Продолжительность готового ролика: от 5 до 7 минут.
- Формат производства: закадровая озвучка, собственные слайды и схемы, при необходимости запись экрана с демонстрацией собственных действий, лицензируемые стоковые материалы.
- Не предполагаются съёмки ведущего в кадре и использование чужих видеороликов без разрешения.
- План должен быть реализуем в автоматизированном конвейере AI Video Factory RU.

ЗАДАНИЕ
Подготовь план ролика, а не полный сценарий. Он должен объяснять тему последовательно, доступно и интересно, а не быть перечнем определений.

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА ОТВЕТА
1. Рабочий заголовок — один основной вариант без кликбейта.
2. Для кого ролик и какую конкретную пользу получит зритель — 2–3 предложения.
3. Центральная мысль ролика — одно предложение.
4. Хук для первых 15–25 секунд — короткий пример закадрового текста.
5. План из 6–8 последовательных блоков в таблице. Для каждого блока укажи:
   - время начала и окончания;
   - название блока;
   - задачу блока;
   - основные тезисы (не более трёх);
   - подходящий визуальный ряд, который реально создать указанными средствами;
   - переход к следующему блоку.
   Суммарная продолжительность блоков должна составлять 5–7 минут. Интервалы времени не должны пересекаться или оставлять необъяснённые промежутки.
6. Два конкретных практических примера применения локального ИИ на обычном компьютере. Не обещай, что любой компьютер справится с любой моделью или задачей.
7. Один содержательный блок об ограничениях и ситуациях, когда локальный запуск не является лучшим выбором.
8. Финал — вывод и естественный призыв к обсуждению, без навязчивой рекламы.
9. Список утверждений, которые редактор должен проверить по актуальным источникам перед написанием полного сценария. Если точные цифры, требования к памяти, названия моделей, версии или сравнения не нужны, не добавляй их ради видимости экспертности.

ТРЕБОВАНИЯ К КАЧЕСТВУ
- Не пиши полный текст озвучки: только пример хука и план.
- Объясняй термины при первом появлении простым языком.
- Не повторяй одну мысль в нескольких блоках.
- Не используй пустые фразы вроде «ИИ меняет мир» или «технологии будущего» без конкретного содержания.
- Не выдумывай статистику, результаты тестов, цены, характеристики компьютеров или минимальные требования к оборудованию.
- Не называй конкретные модели и версии как самые новые или лучшие без проверяемого источника.
- Не утверждай без оговорок, что локальный ИИ всегда полностью приватен, всегда работает без интернета или подходит любому компьютеру.
- Чётко различай локальную обработку на компьютере пользователя и обращение к облачному сервису.
- Не приписывай всем программам запуска моделей одинаковые возможности.
- Визуальные предложения должны помогать понять конкретный тезис, а не быть общими словами «анимация ИИ» или «красивый фон».
- Если тезис требует проверки, пометь его в последнем разделе, а не выдавай как установленный факт.
- Пиши естественным современным русским языком, без канцелярита и чрезмерного пафоса.

ФОРМАТ
Используй Markdown с указанными разделами и одной таблицей. Ответ на русском языке. Не добавляй вступление о том, как ты выполнял задачу.
'@

# UTF-8 without BOM for JSON request files; UTF-8 with BOM for Markdown files
# to improve compatibility with common Windows text editors.
$utf8Bom = [System.Text.UTF8Encoding]::new($true)
$results = @()

$secret = Read-Host 'Введите API-ключ MWS' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:MWS_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($env:MWS_API_KEY)) {
    throw 'API-ключ пуст. Запросы не отправлены.'
}

Add-Type -AssemblyName System.Net.Http
$handler = [System.Net.Http.HttpClientHandler]::new()
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(600)
$client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $env:MWS_API_KEY)

try {
    foreach ($deployment in $deployments) {
        Write-Host "`nЗапуск T2: $($deployment.Id)" -ForegroundColor Cyan

        $requestObject = @{
            model = $deployment.Id
            messages = @(@{ role = 'user'; content = $prompt })
            temperature = 0.2
            max_tokens = 3500
        }
        $requestJson = $requestObject | ConvertTo-Json -Depth 12

        $requestPath = Join-Path $outDir "$($deployment.Name)_request.json"
        $responsePath = Join-Path $outDir "$($deployment.Name)_response.json"
        $answerPath = Join-Path $outDir "$($deployment.Name)_answer.md"
        $metricsPath = Join-Path $outDir "$($deployment.Name)_metrics.json"
        [System.IO.File]::WriteAllText($requestPath, $requestJson, $utf8NoBom)

        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $httpResponse = $null
        try {
            # Send UTF-8 bytes explicitly; read raw response bytes and decode them as UTF-8.
            $requestBytes = [System.Text.Encoding]::UTF8.GetBytes($requestJson)
            $content = [System.Net.Http.ByteArrayContent]::new($requestBytes)
            $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new('application/json')
            $content.Headers.ContentType.CharSet = 'utf-8'

            $httpResponse = $client.PostAsync("$baseUrl/chat/completions", $content).GetAwaiter().GetResult()
            $responseBytes = $httpResponse.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            [System.IO.File]::WriteAllBytes($responsePath, $responseBytes)
            $responseText = [System.Text.Encoding]::UTF8.GetString($responseBytes)
            $stopwatch.Stop()

            if (-not $httpResponse.IsSuccessStatusCode) {
                [System.IO.File]::WriteAllText($answerPath, $responseText, $utf8Bom)
                throw "HTTP $([int]$httpResponse.StatusCode) $($httpResponse.ReasonPhrase): $responseText"
            }

            $apiResult = $responseText | ConvertFrom-Json
            $answer = [string]$apiResult.choices[0].message.content
            if ([string]::IsNullOrWhiteSpace($answer)) {
                throw 'API вернул пустое поле choices[0].message.content.'
            }
            [System.IO.File]::WriteAllText($answerPath, $answer, $utf8Bom)

            $usage = $apiResult.usage
            $promptTokens = [int]$usage.prompt_tokens
            $completionTokens = [int]$usage.completion_tokens
            $totalTokens = [int]$usage.total_tokens
            $estimatedCost = (($promptTokens * $deployment.InputRate) + ($completionTokens * $deployment.OutputRate)) / 1000000

            $reasoningTokens = $null
            if ($usage.completion_tokens_details -and $null -ne $usage.completion_tokens_details.reasoning_tokens) {
                $reasoningTokens = [int]$usage.completion_tokens_details.reasoning_tokens
            }

            $metric = [pscustomobject]@{
                deployment = $deployment.Id
                status = 'success'
                http_status = [int]$httpResponse.StatusCode
                elapsed_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 2)
                prompt_tokens = $promptTokens
                completion_tokens = $completionTokens
                total_tokens = $totalTokens
                reasoning_tokens = $reasoningTokens
                finish_reason = $apiResult.choices[0].finish_reason
                estimated_cost_rub = [Math]::Round([double]$estimatedCost, 6)
                pricing_input_rub_per_million = [double]$deployment.InputRate
                pricing_output_rub_per_million = [double]$deployment.OutputRate
                request_file = $requestPath
                response_file = $responsePath
                answer_file = $answerPath
                encoding = 'UTF-8 (response decoded from raw bytes; answer saved with UTF-8 BOM)'
            }
            $metric | ConvertTo-Json -Depth 10 | Set-Content -Path $metricsPath -Encoding UTF8
            $results += $metric

            Write-Host "Успешно: HTTP $([int]$httpResponse.StatusCode), $($metric.elapsed_seconds) сек." -ForegroundColor Green
            Write-Host "Токены: input=$promptTokens; output=$completionTokens; total=$totalTokens"
            Write-Host "Расчётная стоимость: $($metric.estimated_cost_rub) ₽"
            Write-Host "Ответ сохранён: $answerPath"
            Write-Host "Проверка кириллицы: $([bool]($answer -match '[А-Яа-яЁё]'))"
            Write-Host 'Начало ответа:'
            Write-Host ($answer.Substring(0, [Math]::Min(700, $answer.Length)))
        }
        catch {
            $stopwatch.Stop()
            $errorPath = Join-Path $outDir "$($deployment.Name)_error.txt"
            [System.IO.File]::WriteAllText($errorPath, $_.Exception.ToString(), $utf8Bom)
            Write-Host "Ошибка для $($deployment.Id): $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Подробности сохранены: $errorPath"
        }
        finally {
            if ($httpResponse) { $httpResponse.Dispose() }
        }
    }

    Write-Host "`nСводка T2:" -ForegroundColor Cyan
    $results | Format-Table deployment, status, elapsed_seconds, prompt_tokens, completion_tokens, total_tokens, estimated_cost_rub -AutoSize
    Write-Host "`nВсе файлы: $outDir" -ForegroundColor Cyan
}
finally {
    Remove-Item Env:\MWS_API_KEY -ErrorAction SilentlyContinue
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
}
