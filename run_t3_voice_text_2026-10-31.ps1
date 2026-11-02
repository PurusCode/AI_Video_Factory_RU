# AI Video Factory RU T3 benchmark.
# ASCII-only PowerShell source; Russian prompt is decoded from UTF-8 Base64.
# API key is requested securely and is never written to output files.

$ErrorActionPreference = 'Stop'

$project = 'project-alexsapan'
$baseUrl = "https://gpt.mwsapis.ru/projects/$project/openai/v1"
$outDir = Join-Path $PWD 'output\t3_voice_text_2026-10-31'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$deployments = @(
    [pscustomobject]@{ Name = 'gpt_oss_120b'; Id = 'video-farm-gpt-oss-120b-test'; InputRate = [decimal]13.42; OutputRate = [decimal]54.90 },
    [pscustomobject]@{ Name = 'gemma4_31b'; Id = 'video-farm-gemma-4-31b-test'; InputRate = [decimal]56.12; OutputRate = [decimal]224.48 },
    [pscustomobject]@{ Name = 'qwen36_35b'; Id = 'video-farm-qwen-36-35b-test'; InputRate = [decimal]70.76; OutputRate = [decimal]283.04 }
)

$promptBase64 = @'
0KDQntCb0KwK0KLRiyDigJQg0YDQtdC00LDQutGC0L7RgCDRgtC10LrRgdGC0LAg0LTQu9GPINGA0YPRgdGB0LrQvtC5INGB0LjQvdGC0LXQt9C40YDQvtCy0LDQvdC90L7QuSDRgNC10YfQuC4g0J3Rg9C20L3QviDQv9GA0LXQvtCx0YDQsNC30L7QstCw0YLRjCDQvtC00LjQvSDQuNGB0YXQvtC00L3Ri9C5INGE0YDQsNCz0LzQtdC90YIg0LIg0LTQstCwINC/0L7Qu9GPOiBkaXNwbGF5X3RleHQg0Lggdm9pY2VfdGV4dC4KCtCf0KDQkNCS0JjQm9CQCjEuIGRpc3BsYXlfdGV4dCDQtNC+0LvQttC10L0g0LIg0YLQvtGH0L3QvtGB0YLQuCDQv9C+0LLRgtC+0YDRj9GC0Ywg0LjRgdGF0L7QtNC90YvQuSDRgtC10LrRgdGCLCDQstC60LvRjtGH0LDRjyDRhtC40YTRgNGLLCDQv9GA0L7QsdC10LvRiywg0LfQvdCw0LrQuCDQv9GA0LXQv9C40L3QsNC90LjRjywg0YDQtdCz0LjRgdGC0YAg0Lgg0YLQtdGF0L3QuNGH0LXRgdC60LjQtSDQuNC00LXQvdGC0LjRhNC40LrQsNGC0L7RgNGLLiDQndC1INC40YHQv9GA0LDQstC70Y/QuSwg0L3QtSDQv9C10YDQtdGE0YDQsNC30LjRgNGD0Lkg0Lgg0L3QtSDRhNC+0YDQvNCw0YLQuNGA0YPQuSDQtdCz0L4uCjIuINCSIHZvaWNlX3RleHQg0L/RgNC10L7QsdGA0LDQt9GD0Lkg0YfQuNGB0LvQvtCy0YvQtSDQt9C90LDRh9C10L3QuNGPLCDQvtCx0L7Qt9C90LDRh9Cw0Y7RidC40LUg0LrQvtC70LjRh9C10YHRgtCy0L4sINC00LDRgtGDLCDQtNC70LjRgtC10LvRjNC90L7RgdGC0YwsINC/0YDQvtGG0LXQvdGCINC4INC10LTQuNC90LjRhtGLINC40LfQvNC10YDQtdC90LjRjywg0LIg0LXRgdGC0LXRgdGC0LLQtdC90L3Ri9C1INGA0YPRgdGB0LrQuNC1INGB0LvQvtCy0LXRgdC90YvQtSDRhNC+0YDQvNGLLgozLiDQodC+0LHQu9GO0LTQsNC5INCz0YDQsNC80LzQsNGC0LjRh9C10YHQutC40Lkg0YDQvtC0INC4INC/0LDQtNC10LY6INC90LDQv9GA0LjQvNC10YAsIMKr0YLRgNC4INC90L7QstGL0LUg0LzQvtC00LXQu9C4wrssIMKr0LTQstC1INC30LDQtNCw0YfQuMK7LCDCq9C00LLQtSDQvNC40L3Rg9GC0YvCuywgwqvQv9GP0YLQvdCw0LTRhtCw0YLRjCDRgdC10LrRg9C90LTCuy4KNC4g0JTRgNC+0LHQvdGL0LUg0YfQuNGB0LvQsCDQv9GA0L7QuNC30L3QvtGB0Lgg0YHQu9C+0LLQsNC80Lgg0YEg0LrQvtGA0YDQtdC60YLQvdGL0Lwg0YHQvtCz0LvQsNGB0L7QstCw0L3QuNC10Lwg0LXQtNC40L3QuNGGOiDQvdCw0L/RgNC40LzQtdGALCDCq9C00LLQtdC90LDQtNGG0LDRgtGMINGG0LXQu9GL0YUg0L/Rj9GC0Ywg0LTQtdGB0Y/RgtGL0YUg0L/RgNC+0YbQtdC90YLQsMK7Lgo1LiDQlNCw0YLRiyDQv9GA0L7QuNC30L3QvtGB0Lgg0LXRgdGC0LXRgdGC0LLQtdC90L3QviDQv9C+LdGA0YPRgdGB0LrQuCDRgSDQv9GA0LDQstC40LvRjNC90YvQvNC4INC/0LDQtNC10LbQsNC80LguCjYuINCd0LUg0L/RgNC10L7QsdGA0LDQt9GD0Lkg0YLQtdGF0L3QuNGH0LXRgdC60LjQtSDQuNC00LXQvdGC0LjRhNC40LrQsNGC0L7RgNGLINC4INC+0LHQvtC30L3QsNGH0LXQvdC40Y86IEFQSSB2MS4yLjAsIEhUVFAgMjAwLCBSQU0sIE9sbGFtYSwgV2hpc3Blci5jcHAsIFF3ZW4yLjU6MTRCLCAzQiwgN0Ig0LggMTRCINC00L7Qu9C20L3RiyDQvtGB0YLQsNGC0YzRgdGPINCyIHZvaWNlX3RleHQg0LHQtdC3INC40LfQvNC10L3QtdC90LjRjyDQvdCw0L/QuNGB0LDQvdC40Y8uCjcuINCh0L7RhdGA0LDQvdC4INCy0YHQtSDRhNCw0LrRgtGLLCDRgdC80YvRgdC7LCDQv9C+0YDRj9C00L7QuiDQv9GA0LXQtNC70L7QttC10L3QuNC5LCDRgtC40YDQtSDQuCDQv9GD0L3QutGC0YPQsNGG0LjRjiDQuNGB0YXQvtC00L3QuNC60LAuINCd0LUg0LTQvtCx0LDQstC70Y/QuSDQv9C+0Y/RgdC90LXQvdC40LksINC+0LPQvtCy0L7RgNC+0Log0LjQu9C4INC90L7QstGL0YUg0YHQstC10LTQtdC90LjQuS4KOC4g0J3QtSDQvdC+0YDQvNCw0LvQuNC30YPQuSDQuNC00LXQvdGC0LjRhNC40LrQsNGC0L7RgNGLINC80L7QtNC10LvQtdC5INC60LDQuiDQvtCx0YvRh9C90YvQtSDRh9C40YHQu9C40YLQtdC70YzQvdGL0LUuINCn0LjRgdC70LAg0LIg0L3QsNC30LLQsNC90LjRj9GFINC4INC60L7QtNCw0YUg4oCUINC90LUg0LrQvtC70LjRh9C10YHRgtCy0LAuCjkuINCV0YHQu9C4INGH0LjRgdC70L7QstC+0LUg0LLRi9GA0LDQttC10L3QuNC1INC90LXQvtC00L3QvtC30L3QsNGH0L3Qviwg0L3QtSDQstGL0LTRg9C80YvQstCw0Lkg0LrQvtC90YLQtdC60YHRgjsg0LLRi9Cx0LXRgNC4INC90LDQuNCx0L7Qu9C10LUg0LXRgdGC0LXRgdGC0LLQtdC90L3QvtC1INGH0YLQtdC90LjQtSDRgSDRg9GH0ZHRgtC+0Lwg0L/RgNC10LTQu9C+0LbQtdC90LjRjy4KCtCY0KHQpdCe0JTQndCr0Jkg0KLQldCa0KHQogrQntGC0YfRkdGCINC/0L7QtNCz0L7RgtC+0LLQu9C10L0gMzEuMTAuMjAyNi4g0JIg0YLQtdGB0YLQtSDRg9GH0LDRgdGC0LLQvtCy0LDQu9C4IDMg0L3QvtCy0YvQtSDQvNC+0LTQtdC70Lgg0LggMiDQu9C+0LrQsNC70YzQvdGL0LUg0L/RgNC+0LPRgNCw0LzQvNGLLiDQl9CwIDIg0LzQuNC90YPRgtGLIDE1INGB0LXQutGD0L3QtCDRgdC40YHRgtC10LzQsCDQvtCx0YDQsNCx0L7RgtCw0LvQsCAxIDI0NSDQt9Cw0L/RgNC+0YHQvtCyLiDQodGA0LXQtNC90Y/RjyDQt9Cw0LTQtdGA0LbQutCwINGB0L7RgdGC0LDQstC40LvQsCAxNCw2INGB0LXQutGD0L3QtNGLLCDQsCDQtNC+0LvRjyDRg9GB0L/QtdGI0L3Ri9GFINC+0YLQstC10YLQvtCyIOKAlCA5OCw1JS4g0JTQu9GPINC+0LHRgNCw0LHQvtGC0LrQuCDQuNGB0L/QvtC70YzQt9C+0LLQsNC70L7RgdGMIDcsOCDQk9CRINC+0L/QtdGA0LDRgtC40LLQvdC+0Lkg0L/QsNC80Y/RgtC4LiDQoNC10LfRg9C70YzRgtCw0YLRiyDRgdGA0LDQstC90LjQu9C4INGBIEFQSSB2MS4yLjAg0Lgg0L/RgNC+0LLQtdGA0LjQu9C4INCyIE9sbGFtYSwgV2hpc3Blci5jcHAg0LggUXdlbjIuNToxNEIuINCe0LHQvtC30L3QsNGH0LXQvdC40Y8gM0IsIDdCINC4IDE0QiDigJQg0LjQtNC10L3RgtC40YTQuNC60LDRgtC+0YDRiyDRgNCw0LfQvNC10YDQvtCyINC80L7QtNC10LvQtdC5LCDQsCDQvdC1INC/0L7QutCw0LfQsNGC0LXQu9C4INGB0LrQvtGA0L7RgdGC0LguINCSINC+0YLQtNC10LvRjNC90L7QvCDQttGD0YDQvdCw0LvQtSDQvtGB0YLQsNC70L7RgdGMIDIg0L7RiNC40LHQutC4INC4IDEg0L/RgNC10LTRg9C/0YDQtdC20LTQtdC90LjQtS4g0KHRgtCw0YLRg9GBINC/0YDQvtCy0LXRgNC60Lg6IEhUVFAgMjAwLgoK0KTQntCg0JzQkNCiINCe0KLQktCV0KLQkArQktC10YDQvdC4INGC0L7Qu9GM0LrQviDQstCw0LvQuNC00L3Ri9C5IEpTT04t0L7QsdGK0LXQutGCLCDQsdC10LcgTWFya2Rvd24sINCx0LXQtyDQsdC70L7QutCwINC60L7QtNCwINC4INCx0LXQtyDQtNC+0L/QvtC70L3QuNGC0LXQu9GM0L3QvtCz0L4g0YLQtdC60YHRgtCwLgrQodGC0YDQvtCz0L4g0LTQstCwINGB0YLRgNC+0LrQvtCy0YvRhSDQv9C+0LvRjyDQuCDQuNC80LXQvdC90L4g0LIg0YLQsNC60L7QvCDQv9C+0YDRj9C00LrQtToKewogICJkaXNwbGF5X3RleHQiOiAi0YLQvtGH0L3QsNGPINC60L7Qv9C40Y8g0LjRgdGF0L7QtNC90L7Qs9C+INGC0LXQutGB0YLQsCIsCiAgInZvaWNlX3RleHQiOiAi0YLQtdC60YHRgiwg0L/QvtC00LPQvtGC0L7QstC70LXQvdC90YvQuSDQtNC70Y8g0L7Qt9Cy0YPRh9C60LgiCn0K
'@
$promptBytes = [System.Convert]::FromBase64String(($promptBase64 -replace '\s', ''))
$prompt = [System.Text.UTF8Encoding]::new($false, $true).GetString($promptBytes)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false, $true)
$utf8Bom = [System.Text.UTF8Encoding]::new($true, $true)
$results = @()

$secret = Read-Host 'Enter MWS API key' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:MWS_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($env:MWS_API_KEY)) {
    throw 'API key is empty. No requests were sent.'
}

Add-Type -AssemblyName System.Net.Http
$handler = [System.Net.Http.HttpClientHandler]::new()
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(600)
$client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $env:MWS_API_KEY)

try {
    foreach ($deployment in $deployments) {
        Write-Host "`nT3 request: $($deployment.Id)" -ForegroundColor Cyan

        $requestObject = @{
            model = $deployment.Id
            messages = @(@{ role = 'user'; content = $prompt })
            temperature = 0.2
            max_tokens = 1800
        }
        $requestJson = $requestObject | ConvertTo-Json -Depth 12

        $requestPath = Join-Path $outDir "$($deployment.Name)_request.json"
        $responsePath = Join-Path $outDir "$($deployment.Name)_response.json"
        $answerPath = Join-Path $outDir "$($deployment.Name)_answer.json"
        $metricsPath = Join-Path $outDir "$($deployment.Name)_metrics.json"
        [System.IO.File]::WriteAllText($requestPath, $requestJson, $utf8NoBom)

        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $httpResponse = $null
        try {
            $requestBytes = [System.Text.Encoding]::UTF8.GetBytes($requestJson)
            $content = [System.Net.Http.ByteArrayContent]::new($requestBytes)
            $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new('application/json')
            $content.Headers.ContentType.CharSet = 'utf-8'

            $httpResponse = $client.PostAsync("$baseUrl/chat/completions", $content).GetAwaiter().GetResult()
            $responseBytes = $httpResponse.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            [System.IO.File]::WriteAllBytes($responsePath, $responseBytes)
            $responseText = [System.Text.UTF8Encoding]::new($false, $true).GetString($responseBytes)
            $stopwatch.Stop()

            if (-not $httpResponse.IsSuccessStatusCode) {
                [System.IO.File]::WriteAllText($answerPath, $responseText, $utf8Bom)
                throw "HTTP $([int]$httpResponse.StatusCode) $($httpResponse.ReasonPhrase): $responseText"
            }

            $apiResult = $responseText | ConvertFrom-Json
            $answer = [string]$apiResult.choices[0].message.content
            if ([string]::IsNullOrWhiteSpace($answer)) {
                throw 'API returned an empty choices[0].message.content field.'
            }
            [System.IO.File]::WriteAllText($answerPath, $answer, $utf8Bom)

            $jsonValid = $false
            $jsonError = $null
            try {
                $parsedAnswer = $answer | ConvertFrom-Json -ErrorAction Stop
                $hasDisplay = $null -ne $parsedAnswer.PSObject.Properties['display_text']
                $hasVoice = $null -ne $parsedAnswer.PSObject.Properties['voice_text']
                $jsonValid = ($hasDisplay -and $hasVoice -and $parsedAnswer.PSObject.Properties.Count -eq 2)
                if (-not $jsonValid) { $jsonError = 'Expected exactly display_text and voice_text fields.' }
            } catch {
                $jsonError = $_.Exception.Message
            }

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
                json_valid_with_exact_fields = $jsonValid
                json_validation_error = $jsonError
                answer_file = $answerPath
                encoding = 'UTF-8; raw response bytes decoded explicitly; answer saved with UTF-8 BOM'
            }
            $metric | ConvertTo-Json -Depth 10 | Set-Content -Path $metricsPath -Encoding UTF8
            $results += $metric

            Write-Host "Success: HTTP $([int]$httpResponse.StatusCode), $($metric.elapsed_seconds) sec." -ForegroundColor Green
            Write-Host "Tokens: input=$promptTokens; output=$completionTokens; total=$totalTokens"
            Write-Host "Estimated cost: $($metric.estimated_cost_rub) RUB"
            Write-Host "JSON exact fields valid: $jsonValid"
            if ($jsonError) { Write-Host "JSON validation note: $jsonError" -ForegroundColor Yellow }
            Write-Host "Answer file: $answerPath"
            Write-Host "Cyrillic detected: $([bool]($answer -match '[\u0410-\u042F\u0430-\u044F\u0401\u0451]'))"
        }
        catch {
            $stopwatch.Stop()
            $errorPath = Join-Path $outDir "$($deployment.Name)_error.txt"
            [System.IO.File]::WriteAllText($errorPath, $_.Exception.ToString(), $utf8Bom)
            Write-Host "Request failed for $($deployment.Id): $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Details saved: $errorPath"
        }
        finally {
            if ($httpResponse) { $httpResponse.Dispose() }
        }
    }

    Write-Host "`nT3 summary:" -ForegroundColor Cyan
    $results | Format-Table deployment, status, elapsed_seconds, prompt_tokens, completion_tokens, total_tokens, estimated_cost_rub, json_valid_with_exact_fields -AutoSize
    Write-Host "`nOutput folder: $outDir" -ForegroundColor Cyan
}
finally {
    Remove-Item Env:\MWS_API_KEY -ErrorAction SilentlyContinue
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
}
