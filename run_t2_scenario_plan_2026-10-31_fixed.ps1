# AI Video Factory RU T2 benchmark.
# This script is ASCII-only so Windows PowerShell 5.1 can parse it regardless of the system code page.
# The Russian prompt is stored as UTF-8 Base64 and decoded explicitly at runtime.
# The API key is never written to the output folder.

$ErrorActionPreference = 'Stop'

$project = 'project-alexsapan'
$baseUrl = "https://gpt.mwsapis.ru/projects/$project/openai/v1"
$outDir = Join-Path $PWD 'output\t2_scenario_plan_2026-10-31'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$deployments = @(
    [pscustomobject]@{ Name = 'gpt_oss_120b'; Id = 'video-farm-gpt-oss-120b-test'; InputRate = [decimal]13.42; OutputRate = [decimal]54.90 },
    [pscustomobject]@{ Name = 'gemma4_31b'; Id = 'video-farm-gemma-4-31b-test'; InputRate = [decimal]56.12; OutputRate = [decimal]224.48 },
    [pscustomobject]@{ Name = 'qwen36_35b'; Id = 'video-farm-qwen-36-35b-test'; InputRate = [decimal]70.76; OutputRate = [decimal]283.04 }
)

$promptBase64 = @'
0KDQntCb0KwK0KLRiyDigJQg0L7Qv9GL0YLQvdGL0Lkg0YHRhtC10L3QsNGA0LjRgdGCINC4INGA0LXQtNCw0LrRgtC+0YAg0L7QsdGA0LDQt9C+0LLQsNGC0LXQu9GM0L3QvtCz0L4g0LLQuNC00LXQvtC60LDQvdCw0LvQsCDQvtCxINC40YHQutGD0YHRgdGC0LLQtdC90L3QvtC8INC40L3RgtC10LvQu9C10LrRgtC1LiDQndGD0LbQvdC+INGA0LDQt9GA0LDQsdC+0YLQsNGC0Ywg0L/Qu9Cw0L0g0L7QtNC90L7Qs9C+INC+0LHRitGP0YHQvdGP0Y7RidC10LPQviDQstC40LTQtdC+LgoK0KLQldCc0JAKwqvQp9GC0L4g0YLQsNC60L7QtSDQu9C+0LrQsNC70YzQvdGL0Lkg0JjQmCDQuCDQutC+0LPQtNCwINC+0L0g0L/QvtC70LXQt9C10L0g0L3QsCDQvtCx0YvRh9C90L7QvCDQutC+0LzQv9GM0Y7RgtC10YDQtcK7LgoK0JDQo9CU0JjQotCe0KDQmNCvINCYINCf0KDQntCY0JfQktCe0JTQodCi0JLQngotINCg0YPRgdGB0LrQvtGP0LfRi9GH0L3QsNGPINCw0YPQtNC40YLQvtGA0LjRjywg0L/RgNC10LjQvNGD0YnQtdGB0YLQstC10L3QvdC+INC90L7QstC40YfQutC4LCDQutC+0YLQvtGA0YvQvCDQuNC90YLQtdGA0LXRgdC90L4g0L/RgNCw0LrRgtC40YfQtdGB0LrQvtC1INC/0YDQuNC80LXQvdC10L3QuNC1INCY0JguCi0g0J/RgNC+0LTQvtC70LbQuNGC0LXQu9GM0L3QvtGB0YLRjCDQs9C+0YLQvtCy0L7Qs9C+INGA0L7Qu9C40LrQsDog0L7RgiA1INC00L4gNyDQvNC40L3Rg9GCLgotINCk0L7RgNC80LDRgiDQv9GA0L7QuNC30LLQvtC00YHRgtCy0LA6INC30LDQutCw0LTRgNC+0LLQsNGPINC+0LfQstGD0YfQutCwLCDRgdC+0LHRgdGC0LLQtdC90L3Ri9C1INGB0LvQsNC50LTRiyDQuCDRgdGF0LXQvNGLLCDQv9GA0Lgg0L3QtdC+0LHRhdC+0LTQuNC80L7RgdGC0Lgg0LfQsNC/0LjRgdGMINGN0LrRgNCw0L3QsCDRgSDQtNC10LzQvtC90YHRgtGA0LDRhtC40LXQuSDRgdC+0LHRgdGC0LLQtdC90L3Ri9GFINC00LXQudGB0YLQstC40LksINC70LjRhtC10L3Qt9C40YDRg9C10LzRi9C1INGB0YLQvtC60L7QstGL0LUg0LzQsNGC0LXRgNC40LDQu9GLLgotINCd0LUg0L/RgNC10LTQv9C+0LvQsNCz0LDRjtGC0YHRjyDRgdGK0ZHQvNC60Lgg0LLQtdC00YPRidC10LPQviDQsiDQutCw0LTRgNC1INC4INC40YHQv9C+0LvRjNC30L7QstCw0L3QuNC1INGH0YPQttC40YUg0LLQuNC00LXQvtGA0L7Qu9C40LrQvtCyINCx0LXQtyDRgNCw0LfRgNC10YjQtdC90LjRjy4KLSDQn9C70LDQvSDQtNC+0LvQttC10L0g0LHRi9GC0Ywg0YDQtdCw0LvQuNC30YPQtdC8INCyINCw0LLRgtC+0LzQsNGC0LjQt9C40YDQvtCy0LDQvdC90L7QvCDQutC+0L3QstC10LnQtdGA0LUgQUkgVmlkZW8gRmFjdG9yeSBSVS4KCtCX0JDQlNCQ0J3QmNCVCtCf0L7QtNCz0L7RgtC+0LLRjCDQv9C70LDQvSDRgNC+0LvQuNC60LAsINCwINC90LUg0L/QvtC70L3Ri9C5INGB0YbQtdC90LDRgNC40LkuINCe0L0g0LTQvtC70LbQtdC9INC+0LHRitGP0YHQvdGP0YLRjCDRgtC10LzRgyDQv9C+0YHQu9C10LTQvtCy0LDRgtC10LvRjNC90L4sINC00L7RgdGC0YPQv9C90L4g0Lgg0LjQvdGC0LXRgNC10YHQvdC+LCDQsCDQvdC1INCx0YvRgtGMINC/0LXRgNC10YfQvdC10Lwg0L7Qv9GA0LXQtNC10LvQtdC90LjQuS4KCtCe0JHQr9CX0JDQotCV0JvQrNCd0JDQryDQodCi0KDQo9Ca0KLQo9Cg0JAg0J7QotCS0JXQotCQCjEuINCg0LDQsdC+0YfQuNC5INC30LDQs9C+0LvQvtCy0L7QuiDigJQg0L7QtNC40L0g0L7RgdC90L7QstC90L7QuSDQstCw0YDQuNCw0L3RgiDQsdC10Lcg0LrQu9C40LrQsdC10LnRgtCwLgoyLiDQlNC70Y8g0LrQvtCz0L4g0YDQvtC70LjQuiDQuCDQutCw0LrRg9GOINC60L7QvdC60YDQtdGC0L3Rg9GOINC/0L7Qu9GM0LfRgyDQv9C+0LvRg9GH0LjRgiDQt9GA0LjRgtC10LvRjCDigJQgMuKAkzMg0L/RgNC10LTQu9C+0LbQtdC90LjRjy4KMy4g0KbQtdC90YLRgNCw0LvRjNC90LDRjyDQvNGL0YHQu9GMINGA0L7Qu9C40LrQsCDigJQg0L7QtNC90L4g0L/RgNC10LTQu9C+0LbQtdC90LjQtS4KNC4g0KXRg9C6INC00LvRjyDQv9C10YDQstGL0YUgMTXigJMyNSDRgdC10LrRg9C90LQg4oCUINC60L7RgNC+0YLQutC40Lkg0L/RgNC40LzQtdGAINC30LDQutCw0LTRgNC+0LLQvtCz0L4g0YLQtdC60YHRgtCwLgo1LiDQn9C70LDQvSDQuNC3IDbigJM4INC/0L7RgdC70LXQtNC+0LLQsNGC0LXQu9GM0L3Ri9GFINCx0LvQvtC60L7QsiDQsiDRgtCw0LHQu9C40YbQtS4g0JTQu9GPINC60LDQttC00L7Qs9C+INCx0LvQvtC60LAg0YPQutCw0LbQuDoKICAgLSDQstGA0LXQvNGPINC90LDRh9Cw0LvQsCDQuCDQvtC60L7QvdGH0LDQvdC40Y87CiAgIC0g0L3QsNC30LLQsNC90LjQtSDQsdC70L7QutCwOwogICAtINC30LDQtNCw0YfRgyDQsdC70L7QutCwOwogICAtINC+0YHQvdC+0LLQvdGL0LUg0YLQtdC30LjRgdGLICjQvdC1INCx0L7Qu9C10LUg0YLRgNGR0YUpOwogICAtINC/0L7QtNGF0L7QtNGP0YnQuNC5INCy0LjQt9GD0LDQu9GM0L3Ri9C5INGA0Y/QtCwg0LrQvtGC0L7RgNGL0Lkg0YDQtdCw0LvRjNC90L4g0YHQvtC30LTQsNGC0Ywg0YPQutCw0LfQsNC90L3Ri9C80Lgg0YHRgNC10LTRgdGC0LLQsNC80Lg7CiAgIC0g0L/QtdGA0LXRhdC+0LQg0Log0YHQu9C10LTRg9GO0YnQtdC80YMg0LHQu9C+0LrRgy4KICAg0KHRg9C80LzQsNGA0L3QsNGPINC/0YDQvtC00L7Qu9C20LjRgtC10LvRjNC90L7RgdGC0Ywg0LHQu9C+0LrQvtCyINC00L7Qu9C20L3QsCDRgdC+0YHRgtCw0LLQu9GP0YLRjCA14oCTNyDQvNC40L3Rg9GCLiDQmNC90YLQtdGA0LLQsNC70Ysg0LLRgNC10LzQtdC90Lgg0L3QtSDQtNC+0LvQttC90Ysg0L/QtdGA0LXRgdC10LrQsNGC0YzRgdGPINC40LvQuCDQvtGB0YLQsNCy0LvRj9GC0Ywg0L3QtdC+0LHRitGP0YHQvdGR0L3QvdGL0LUg0L/RgNC+0LzQtdC20YPRgtC60LguCjYuINCU0LLQsCDQutC+0L3QutGA0LXRgtC90YvRhSDQv9GA0LDQutGC0LjRh9C10YHQutC40YUg0L/RgNC40LzQtdGA0LAg0L/RgNC40LzQtdC90LXQvdC40Y8g0LvQvtC60LDQu9GM0L3QvtCz0L4g0JjQmCDQvdCwINC+0LHRi9GH0L3QvtC8INC60L7QvNC/0YzRjtGC0LXRgNC1LiDQndC1INC+0LHQtdGJ0LDQuSwg0YfRgtC+INC70Y7QsdC+0Lkg0LrQvtC80L/RjNGO0YLQtdGAINGB0L/RgNCw0LLQuNGC0YHRjyDRgSDQu9GO0LHQvtC5INC80L7QtNC10LvRjNGOINC40LvQuCDQt9Cw0LTQsNGH0LXQuS4KNy4g0J7QtNC40L0g0YHQvtC00LXRgNC20LDRgtC10LvRjNC90YvQuSDQsdC70L7QuiDQvtCxINC+0LPRgNCw0L3QuNGH0LXQvdC40Y/RhSDQuCDRgdC40YLRg9Cw0YbQuNGP0YUsINC60L7Qs9C00LAg0LvQvtC60LDQu9GM0L3Ri9C5INC30LDQv9GD0YHQuiDQvdC1INGP0LLQu9GP0LXRgtGB0Y8g0LvRg9GH0YjQuNC8INCy0YvQsdC+0YDQvtC8Lgo4LiDQpNC40L3QsNC7IOKAlCDQstGL0LLQvtC0INC4INC10YHRgtC10YHRgtCy0LXQvdC90YvQuSDQv9GA0LjQt9GL0LIg0Log0L7QsdGB0YPQttC00LXQvdC40Y4sINCx0LXQtyDQvdCw0LLRj9C30YfQuNCy0L7QuSDRgNC10LrQu9Cw0LzRiy4KOS4g0KHQv9C40YHQvtC6INGD0YLQstC10YDQttC00LXQvdC40LksINC60L7RgtC+0YDRi9C1INGA0LXQtNCw0LrRgtC+0YAg0LTQvtC70LbQtdC9INC/0YDQvtCy0LXRgNC40YLRjCDQv9C+INCw0LrRgtGD0LDQu9GM0L3Ri9C8INC40YHRgtC+0YfQvdC40LrQsNC8INC/0LXRgNC10LQg0L3QsNC/0LjRgdCw0L3QuNC10Lwg0L/QvtC70L3QvtCz0L4g0YHRhtC10L3QsNGA0LjRjy4g0JXRgdC70Lgg0YLQvtGH0L3Ri9C1INGG0LjRhNGA0YssINGC0YDQtdCx0L7QstCw0L3QuNGPINC6INC/0LDQvNGP0YLQuCwg0L3QsNC30LLQsNC90LjRjyDQvNC+0LTQtdC70LXQuSwg0LLQtdGA0YHQuNC4INC40LvQuCDRgdGA0LDQstC90LXQvdC40Y8g0L3QtSDQvdGD0LbQvdGLLCDQvdC1INC00L7QsdCw0LLQu9GP0Lkg0LjRhSDRgNCw0LTQuCDQstC40LTQuNC80L7RgdGC0Lgg0Y3QutGB0L/QtdGA0YLQvdC+0YHRgtC4LgoK0KLQoNCV0JHQntCS0JDQndCY0K8g0Jog0JrQkNCn0JXQodCi0JLQowotINCd0LUg0L/QuNGI0Lgg0L/QvtC70L3Ri9C5INGC0LXQutGB0YIg0L7Qt9Cy0YPRh9C60Lg6INGC0L7Qu9GM0LrQviDQv9GA0LjQvNC10YAg0YXRg9C60LAg0Lgg0L/Qu9Cw0L0uCi0g0J7QsdGK0Y/RgdC90Y/QuSDRgtC10YDQvNC40L3RiyDQv9GA0Lgg0L/QtdGA0LLQvtC8INC/0L7Rj9Cy0LvQtdC90LjQuCDQv9GA0L7RgdGC0YvQvCDRj9C30YvQutC+0LwuCi0g0J3QtSDQv9C+0LLRgtC+0YDRj9C5INC+0LTQvdGDINC80YvRgdC70Ywg0LIg0L3QtdGB0LrQvtC70YzQutC40YUg0LHQu9C+0LrQsNGFLgotINCd0LUg0LjRgdC/0L7Qu9GM0LfRg9C5INC/0YPRgdGC0YvQtSDRhNGA0LDQt9GLINCy0YDQvtC00LUgwqvQmNCYINC80LXQvdGP0LXRgiDQvNC40YDCuyDQuNC70LggwqvRgtC10YXQvdC+0LvQvtCz0LjQuCDQsdGD0LTRg9GJ0LXQs9C+wrsg0LHQtdC3INC60L7QvdC60YDQtdGC0L3QvtCz0L4g0YHQvtC00LXRgNC20LDQvdC40Y8uCi0g0J3QtSDQstGL0LTRg9C80YvQstCw0Lkg0YHRgtCw0YLQuNGB0YLQuNC60YMsINGA0LXQt9GD0LvRjNGC0LDRgtGLINGC0LXRgdGC0L7Qsiwg0YbQtdC90YssINGF0LDRgNCw0LrRgtC10YDQuNGB0YLQuNC60Lgg0LrQvtC80L/RjNGO0YLQtdGA0L7QsiDQuNC70Lgg0LzQuNC90LjQvNCw0LvRjNC90YvQtSDRgtGA0LXQsdC+0LLQsNC90LjRjyDQuiDQvtCx0L7RgNGD0LTQvtCy0LDQvdC40Y4uCi0g0J3QtSDQvdCw0LfRi9Cy0LDQuSDQutC+0L3QutGA0LXRgtC90YvQtSDQvNC+0LTQtdC70Lgg0Lgg0LLQtdGA0YHQuNC4INC60LDQuiDRgdCw0LzRi9C1INC90L7QstGL0LUg0LjQu9C4INC70YPRh9GI0LjQtSDQsdC10Lcg0L/RgNC+0LLQtdGA0Y/QtdC80L7Qs9C+INC40YHRgtC+0YfQvdC40LrQsC4KLSDQndC1INGD0YLQstC10YDQttC00LDQuSDQsdC10Lcg0L7Qs9C+0LLQvtGA0L7Quiwg0YfRgtC+INC70L7QutCw0LvRjNC90YvQuSDQmNCYINCy0YHQtdCz0LTQsCDQv9C+0LvQvdC+0YHRgtGM0Y4g0L/RgNC40LLQsNGC0LXQvSwg0LLRgdC10LPQtNCwINGA0LDQsdC+0YLQsNC10YIg0LHQtdC3INC40L3RgtC10YDQvdC10YLQsCDQuNC70Lgg0L/QvtC00YXQvtC00LjRgiDQu9GO0LHQvtC80YMg0LrQvtC80L/RjNGO0YLQtdGA0YMuCi0g0KfRkdGC0LrQviDRgNCw0LfQu9C40YfQsNC5INC70L7QutCw0LvRjNC90YPRjiDQvtCx0YDQsNCx0L7RgtC60YMg0L3QsCDQutC+0LzQv9GM0Y7RgtC10YDQtSDQv9C+0LvRjNC30L7QstCw0YLQtdC70Y8g0Lgg0L7QsdGA0LDRidC10L3QuNC1INC6INC+0LHQu9Cw0YfQvdC+0LzRgyDRgdC10YDQstC40YHRgy4KLSDQndC1INC/0YDQuNC/0LjRgdGL0LLQsNC5INCy0YHQtdC8INC/0YDQvtCz0YDQsNC80LzQsNC8INC30LDQv9GD0YHQutCwINC80L7QtNC10LvQtdC5INC+0LTQuNC90LDQutC+0LLRi9C1INCy0L7Qt9C80L7QttC90L7RgdGC0LguCi0g0JLQuNC30YPQsNC70YzQvdGL0LUg0L/RgNC10LTQu9C+0LbQtdC90LjRjyDQtNC+0LvQttC90Ysg0L/QvtC80L7Qs9Cw0YLRjCDQv9C+0L3Rj9GC0Ywg0LrQvtC90LrRgNC10YLQvdGL0Lkg0YLQtdC30LjRgSwg0LAg0L3QtSDQsdGL0YLRjCDQvtCx0YnQuNC80Lgg0YHQu9C+0LLQsNC80LggwqvQsNC90LjQvNCw0YbQuNGPINCY0JjCuyDQuNC70LggwqvQutGA0LDRgdC40LLRi9C5INGE0L7QvcK7LgotINCV0YHQu9C4INGC0LXQt9C40YEg0YLRgNC10LHRg9C10YIg0L/RgNC+0LLQtdGA0LrQuCwg0L/QvtC80LXRgtGMINC10LPQviDQsiDQv9C+0YHQu9C10LTQvdC10Lwg0YDQsNC30LTQtdC70LUsINCwINC90LUg0LLRi9C00LDQstCw0Lkg0LrQsNC6INGD0YHRgtCw0L3QvtCy0LvQtdC90L3Ri9C5INGE0LDQutGCLgotINCf0LjRiNC4INC10YHRgtC10YHRgtCy0LXQvdC90YvQvCDRgdC+0LLRgNC10LzQtdC90L3Ri9C8INGA0YPRgdGB0LrQuNC8INGP0LfRi9C60L7QvCwg0LHQtdC3INC60LDQvdGG0LXQu9GP0YDQuNGC0LAg0Lgg0YfRgNC10LfQvNC10YDQvdC+0LPQviDQv9Cw0YTQvtGB0LAuCgrQpNCe0KDQnNCQ0KIK0JjRgdC/0L7Qu9GM0LfRg9C5IE1hcmtkb3duINGBINGD0LrQsNC30LDQvdC90YvQvNC4INGA0LDQt9C00LXQu9Cw0LzQuCDQuCDQvtC00L3QvtC5INGC0LDQsdC70LjRhtC10LkuINCe0YLQstC10YIg0L3QsCDRgNGD0YHRgdC60L7QvCDRj9C30YvQutC1LiDQndC1INC00L7QsdCw0LLQu9GP0Lkg0LLRgdGC0YPQv9C70LXQvdC40LUg0L4g0YLQvtC8LCDQutCw0Log0YLRiyDQstGL0L/QvtC70L3Rj9C7INC30LDQtNCw0YfRgy4=
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
        Write-Host "`nT2 request: $($deployment.Id)" -ForegroundColor Cyan

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
            # Send explicit UTF-8 request bytes and decode raw response bytes as UTF-8.
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
                encoding = 'UTF-8; raw response bytes decoded explicitly; Markdown saved with UTF-8 BOM'
            }
            $metric | ConvertTo-Json -Depth 10 | Set-Content -Path $metricsPath -Encoding UTF8
            $results += $metric

            Write-Host "Success: HTTP $([int]$httpResponse.StatusCode), $($metric.elapsed_seconds) sec." -ForegroundColor Green
            Write-Host "Tokens: input=$promptTokens; output=$completionTokens; total=$totalTokens"
            Write-Host "Estimated cost: $($metric.estimated_cost_rub) RUB"
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

    Write-Host "`nT2 summary:" -ForegroundColor Cyan
    $results | Format-Table deployment, status, elapsed_seconds, prompt_tokens, completion_tokens, total_tokens, estimated_cost_rub -AutoSize
    Write-Host "`nOutput folder: $outDir" -ForegroundColor Cyan
}
finally {
    Remove-Item Env:\MWS_API_KEY -ErrorAction SilentlyContinue
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
}
