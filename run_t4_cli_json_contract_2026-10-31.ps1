# AI Video Factory RU - T4 CLI JSON contract benchmark.
# ASCII-only source for Windows PowerShell 5.1; Russian prompts are UTF-8 Base64.
# API keys are read securely and are never written to output files.

$ErrorActionPreference = 'Stop'
$project = 'project-alexsapan'
$mwsBaseUrl = "https://gpt.mwsapis.ru/projects/$project/openai/v1"
$outDir = Join-Path $PWD 'output\t4_cli_json_contract_2026-10-31'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$systemPrompt = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('0KLRiyDigJQg0YHRhtC10L3QsNGA0LjRgdGCINGA0YPRgdGB0LrQvtGP0LfRi9GH0L3QvtCz0L4g0YLQtdGF0L3QvtC70L7Qs9C40YfQtdGB0LrQvtCz0L4g0LrQsNC90LDQu9CwLiDQn9C40YjQuCDRj9GB0L3QviDQuCDRgNCw0LfQs9C+0LLQvtGA0L3Qvi4g0J3QtSDQstGL0LTRg9C80YvQstCw0Lkg0YLQvtGH0L3Ri9C1INGG0LjRhNGA0YssINGF0LDRgNCw0LrRgtC10YDQuNGB0YLQuNC60LgsINCy0LXRgNGB0LjQuCwg0YbQtdC90YssINGA0LXQt9GD0LvRjNGC0LDRgtGLINGC0LXRgdGC0L7Qsiwg0YHRgdGL0LvQutC4INC4INGG0LjRgtCw0YLRiy4g0J3QtSDQvtCx0LXRidCw0Lkg0LDQsdGB0L7Qu9GO0YLQvdGD0Y4g0L/RgNC40LLQsNGC0L3QvtGB0YLRjCwg0LPQsNGA0LDQvdGC0LjRgNC+0LLQsNC90L3Rg9GOINCx0LXQt9C+0L/QsNGB0L3QvtGB0YLRjCDQuNC70Lgg0L/QvtC70L3Rg9GOINCw0LLRgtC+0L3QvtC80L3QvtGB0YLRjC4g0JXRgdC70Lgg0YPRgtCy0LXRgNC20LTQtdC90LjQtSDRgtGA0LXQsdGD0LXRgiDQv9GA0L7QstC10YDQutC4LCDQstC60LvRjtGH0Lgg0LXQs9C+INCyIGZhY3RfY2hlY2tzOyDQtdGB0LvQuCDQuNGB0YLQvtGH0L3QuNC6INC90LUg0L/RgNC10LTQvtGB0YLQsNCy0LvQtdC9LCBzb3VyY2VfdXJsINC+0YHRgtCw0LLRjCDQv9GD0YHRgtC+0Lkg0YHRgtGA0L7QutC+0LksIHN0YXR1cyDRg9GB0YLQsNC90L7QstC4INCyIHZlcmlmeV9iZWZvcmVfcHVibGlzaC4g0JLQtdGA0L3QuCDRgtC+0LvRjNC60L4g0L7QtNC40L0g0LrQvtGA0YDQtdC60YLQvdGL0LkgSlNPTi3QvtCx0YrQtdC60YIsINCx0LXQtyBNYXJrZG93biDQuCDQv9C+0Y/RgdC90LXQvdC40Lku'))
$userPrompt = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('0J/QvtC00LPQvtGC0L7QstGMINCa0J7QoNCe0KLQmtCY0Jkg0YHRgtGA0YPQutGC0YPRgNC90YvQuSDQvNCw0LrQtdGCINGB0YbQtdC90LDRgNC40Y8g0LTQu9GPINGA0L7Qu9C40LrQsCDQvdCwINGC0LXQvNGDOiDCq9Cn0YLQviDRgtCw0LrQvtC1INC70L7QutCw0LvRjNC90YvQuSDQmNCYINC4INC60L7Qs9C00LAg0L7QvSDQv9C+0LvQtdC30LXQvSDQvdCwINC+0LHRi9GH0L3QvtC8INC60L7QvNC/0YzRjtGC0LXRgNC1wrsuCgrQmNGB0YLQvtGH0L3QuNC60Lgg0Lgg0YDQtdC30YPQu9GM0YLQsNGC0Ysg0LjRgdC/0YvRgtCw0L3QuNC5INC90LUg0L/RgNC10LTQvtGB0YLQsNCy0LvQtdC90YsuINCt0YLQviDRgtC10YHRgiDRgdGC0YDRg9C60YLRg9GA0YsgSlNPTiwg0LAg0L3QtSDQuNGB0YHQu9C10LTQvtCy0LDQvdC40LUg0Lgg0L3QtSDQv9C+0LvQvdGL0LkgcHJvZHVjdGlvbi3RgdGG0LXQvdCw0YDQuNC5LiDQndC1INGD0LrQsNC30YvQstCw0Lkg0LrQvtC90LrRgNC10YLQvdGL0LUg0YLRgNC10LHQvtCy0LDQvdC40Y8g0LogUkFNL1ZSQU0sINGB0LrQvtGA0L7RgdGC0YwsINGB0YLQvtC40LzQvtGB0YLRjCwg0L/RgNC+0YbQtdC90YLRiywg0LPQsNGA0LDQvdGC0LjQuCDQv9GA0LjQstCw0YLQvdC+0YHRgtC4INC40LvQuCDQsNC60YLRg9Cw0LvRjNC90YvQtSDQstC10YDRgdC40Lgg0L/RgNC+0LTRg9C60YLQvtCyLgoK0JLQtdGA0L3QuCDQvtC00LjQvSBKU09OLdC+0LHRitC10LrRgi4gVG9wLWxldmVsINC/0L7Qu9GPICjQstGB0LUg0L7QsdGP0LfQsNGC0LXQu9GM0L3Riyk6Ci0gdGl0bGU6INGB0YLRgNC+0LrQsCDQtNC70LjQvdC+0LkgNTXigJM3MCDRgdC40LzQstC+0LvQvtCyLCDQsdC10Lcg0L3QtdC00L7QutCw0LfRg9C10LzRi9GFINC+0LHQtdGJ0LDQvdC40Lk7Ci0gdG9waWM6INGB0YLRgNC+0LrQsCDRgSDRgtC10LzQvtC5OwotIGRlc2NyaXB0aW9uX3N1bW1hcnk6INGA0L7QstC90L4gMiDQv9GA0LXQtNC70L7QttC10L3QuNGPOwotIGhhc2h0YWdzOiDQvNCw0YHRgdC40LIg0LjQtyA14oCTOCDRgdGC0YDQvtC6OwotIHRhcmdldF9kdXJhdGlvbl9taW51dGVzOiDRh9C40YHQu9C+IDg7Ci0gZmFjdF9jaGVja3M6INC80LDRgdGB0LjQsiDQvtCx0YrQtdC60YLQvtCyINGBINC/0L7Qu9GP0LzQuCBjbGFpbSwgc291cmNlX3VybCwgc3RhdHVzOyBzb3VyY2VfdXJsINC/0YPRgdGC0LDRjyDRgdGC0YDQvtC60LAsINC10YHQu9C4INC40YHRgtC+0YfQvdC40Log0L3QtSDQv9GA0LXQtNC+0YHRgtCw0LLQu9C10L07IHN0YXR1cyA9ICJ2ZXJpZnlfYmVmb3JlX3B1Ymxpc2giOwotIG11c2ljX3BvbGljeTog0YHRgtGA0L7QutCwINC+INGC0L7QvCwg0YfRgtC+INC80YPQt9GL0LrQsCDQvdC1INC40YHQv9C+0LvRjNC30YPQtdGC0YHRjyDQsdC10Lcg0L/QvtC00YLQstC10YDQttC00ZHQvdC90L7QuSDQutC+0LzQvNC10YDRh9C10YHQutC+0Lkg0LvQuNGG0LXQvdC30LjQuDsKLSBibG9ja3M6INC80LDRgdGB0LjQsiDRgNC+0LLQvdC+INC40LcgNyDQsdC70L7QutC+0LIg0LIg0YHQu9C10LTRg9GO0YnQtdC8INC/0L7RgNGP0LTQutC1OiBob29rLCBzZWN0aW9uLCBzZWN0aW9uLCBzZWN0aW9uLCBzZWN0aW9uLCBzZWN0aW9uLCBjdGEuCgrQmtCw0LbQtNGL0Lkg0LHQu9C+0Log0YHQvtC00LXRgNC20LjRgiDRgNC+0LLQvdC+INGN0YLQuCDQv9C+0LvRjzoKLSBpZDog0YPQvdC40LrQsNC70YzQvdCw0Y8g0YHRgtGA0L7QutCwIGJsb2NrXzAxIC4uLiBibG9ja18wNzsKLSBraW5kOiDQvtC00L3QviDQuNC3IGhvb2ssIHNlY3Rpb24sIGN0YTsKLSBoZWFkaW5nOiDQutC+0YDQvtGC0LrQuNC5INC30LDQs9C+0LvQvtCy0L7QujsKLSB2b2ljZV90ZXh0OiDRgdCy0Y/Qt9C90YvQuSDRgtC10LrRgdGCINC90LAg0YDRg9GB0YHQutC+0Lwg0L/RgNC40LzQtdGA0L3QviA0MOKAkzYwINGB0LvQvtCyINC00LvRjyDRjdGC0L7Qs9C+INC60L7RgNC+0YLQutC+0LPQviDRgtC10YHRgtCwOwotIHNsaWRlczog0LzQsNGB0YHQuNCyINGA0L7QstC90L4g0LjQtyAzINGB0LvQsNC50LTQvtCyOwotIGJyb2xsX2tleXdvcmRzOiDQvNCw0YHRgdC40LIg0LjQtyAy4oCTNSDQutC+0YDQvtGC0LrQuNGFINCw0L3Qs9C70L7Rj9C30YvRh9C90YvRhSDQv9C+0LjRgdC60L7QstGL0YUg0YTRgNCw0LcuCgrQmtCw0LbQtNGL0Lkg0YHQu9Cw0LnQtCDRgdC+0LTQtdGA0LbQuNGCINGA0L7QstC90L4g0Y3RgtC4INC/0L7Qu9GPOgotIHR5cGU6INC+0LTQvdC+INC40LcgdGV4dCwgbWV0cmljLCBjb21wYXJpc29uLCBxdW90ZSwgbGlzdCwgYmFyX2NoYXJ0LCBwcm9ncmVzcywgcGhvdG8sIHNwbGl0LCBzdG9yeWJvYXJkOwotIHRpdGxlOiDQutC+0YDQvtGC0LrQuNC5INC30LDQs9C+0LvQvtCy0L7QujsKLSBib2R5OiDQutC+0YDQvtGC0LrQsNGPINGE0YDQsNC30LAgKNC+0LHRi9GH0L3QviDQtNC+IDcg0YHQu9C+0LIpOwotIG1ldHJpYzog0YHRgtGA0L7QutCwINC40LvQuCDQv9GD0YHRgtCw0Y8g0YHRgtGA0L7QutCwOyDQvdC1INC/0YDQuNC00YPQvNGL0LLQsNC5INGH0LjRgdC70L7QstGL0LUg0LzQtdGC0YDQuNC60Lg7Ci0gcGhvdG9fa2V5d29yZDog0LDQvdCz0LvQuNC50YHQutC40Lkg0L/QvtC40YHQutC+0LLRi9C5INC30LDQv9GA0L7RgSDQuNC70Lgg0L/Rg9GB0YLQsNGPINGB0YLRgNC+0LrQsDsKLSBpdGVtczog0LzQsNGB0YHQuNCyINGB0YLRgNC+0LogKNC80L7QttC10YIg0LHRi9GC0Ywg0L/Rg9GB0YLRi9C8KTsKLSBzb3VyY2U6IFVSTCDQuNGB0YLQvtGH0L3QuNC60LAg0LjQu9C4INC/0YPRgdGC0LDRjyDRgdGC0YDQvtC60LAsINC/0L7RgdC60L7Qu9GM0LrRgyDQuNGB0YLQvtGH0L3QuNC60Lgg0L3QtSDQv9C10YDQtdC00LDQvdGLLgoK0KLQtdC80Ysg0YHQtdC80Lgg0LHQu9C+0LrQvtCyINC/0L4g0L/QvtGA0Y/QtNC60YM6CjEpIGhvb2sg4oCUINC30LDRhtC10L/QutCwINC4INCy0L7Qv9GA0L7RgSwg0YfRgtC+INC30L3QsNGH0LjRgiDCq9C70L7QutCw0LvRjNC90YvQucK7OwoyKSBzZWN0aW9uIOKAlCDQv9GA0L7RgdGC0L7QtSDQvtCx0YrRj9GB0L3QtdC90LjQtSwg0LPQtNC1INGA0LDQsdC+0YLQsNC10YIg0LzQvtC00LXQu9GMOwozKSBzZWN0aW9uIOKAlCDQv9GA0LjQvNC10YDRiyDQt9Cw0LTQsNGHLCDQtNC70Y8g0LrQvtGC0L7RgNGL0YUg0L7QvdCwINC80L7QttC10YIg0L/RgNC40LPQvtC00LjRgtGM0YHRjzsKNCkgc2VjdGlvbiDigJQg0LLQvtC30LzQvtC20L3Ri9C1INC/0YDQtdC40LzRg9GJ0LXRgdGC0LLQsCDQu9C+0LrQsNC70YzQvdC+0Lkg0L7QsdGA0LDQsdC+0YLQutC4INCx0LXQtyDQsNCx0YHQvtC70Y7RgtC90YvRhSDQs9Cw0YDQsNC90YLQuNC5Owo1KSBzZWN0aW9uIOKAlCDQvtCz0YDQsNC90LjRh9C10L3QuNGPOiDRgNC10YHRg9GA0YHRiyDQutC+0LzQv9GM0Y7RgtC10YDQsCwg0LrQsNGH0LXRgdGC0LLQviwg0L3QsNGB0YLRgNC+0LnQutCwINC4INC+0LHQvdC+0LLQu9C10L3QuNC1Owo2KSBzZWN0aW9uIOKAlCDQutCw0Log0YDQtdGI0LjRgtGMLCDQv9C+0LTRhdC+0LTQuNGCINC70Lgg0LvQvtC60LDQu9GM0L3Ri9C5INCy0LDRgNC40LDQvdGCINC60L7QvdC60YDQtdGC0L3QvtC80YMg0YfQtdC70L7QstC10LrRgzsKNykgY3RhIOKAlCDQutGA0LDRgtC60LjQuSDQstGL0LLQvtC0INC4INC90LXQudGC0YDQsNC70YzQvdGL0Lkg0L/RgNC40LfRi9CyINC+0YbQtdC90LjRgtGMINGB0L7QsdGB0YLQstC10L3QvdGD0Y4g0LfQsNC00LDRh9GDLgoK0KHQvtC00LXRgNC20LjQvNC+0LUg0LrQsNC20LTQvtCz0L4g0YHQu9Cw0LnQtNCwINC00L7Qu9C20L3QviDRgdC+0L7RgtCy0LXRgtGB0YLQstC+0LLQsNGC0Ywgdm9pY2VfdGV4dCDRgdCy0L7QtdCz0L4g0LHQu9C+0LrQsC4g0J3QtSDQstGL0LTRg9C80YvQstCw0Lkg0YbQuNGC0LDRgtGLLCDQuNGB0YLQvtGH0L3QuNC60Lgg0LjQu9C4INGB0YDQsNCy0L3QuNGC0LXQu9GM0L3Ri9C1INGA0LXQt9GD0LvRjNGC0LDRgtGLLiDQktC10YDQvdC4INGC0L7Qu9GM0LrQviBKU09OOiDQvdC40LrQsNC60LjRhSBgYGBqc29uLCDQstGB0YLRg9C/0LvQtdC90LjRjywg0LfQsNC60LvRjtGH0LXQvdC40Y8g0LjQu9C4INC60L7QvNC80LXQvdGC0LDRgNC40LXQsi4g0KHQvtCx0LvRjtC00LDQuSDRgtC+0YfQvdGL0LUg0LjQvNC10L3QsCDQuCDRgtC40L/RiyDQv9C+0LvQtdC5Lg=='))

$models = @(
    [pscustomobject]@{ Name = 'gpt_oss_120b'; Model = 'video-farm-gpt-oss-120b-test'; BaseUrl = $mwsBaseUrl; ApiKey = ''; Provider = 'MWS' },
    [pscustomobject]@{ Name = 'gemma4_31b'; Model = 'video-farm-gemma-4-31b-test'; BaseUrl = $mwsBaseUrl; ApiKey = ''; Provider = 'MWS' },
    [pscustomobject]@{ Name = 'qwen36_35b'; Model = 'video-farm-qwen-36-35b-test'; BaseUrl = $mwsBaseUrl; ApiKey = ''; Provider = 'MWS' },
    [pscustomobject]@{ Name = 'ollama_qwen25_14b'; Model = 'qwen2.5:14b-instruct'; BaseUrl = 'http://localhost:11434/v1'; ApiKey = 'ollama'; Provider = 'Ollama' }
)

# Read the MWS token once. The plain string exists only in this PowerShell process.
$secure = Read-Host 'MWS API key (input hidden)' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $mwsKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if ([string]::IsNullOrWhiteSpace($mwsKey)) { throw 'MWS API key cannot be empty.' }
foreach ($m in $models) { if ($m.Provider -eq 'MWS') { $m.ApiKey = $mwsKey } }

function Get-PropNames($object) {
    if ($null -eq $object) { return @() }
    return @($object.PSObject.Properties | ForEach-Object { $_.Name })
}

function Test-ExactFields($object, [string[]]$expected, [string]$label, [System.Collections.Generic.List[string]]$errors) {
    if ($null -eq $object -or $object -is [System.Array] -or $object -is [string]) {
        $errors.Add("$label is not a JSON object")
        return
    }
    $actual = @(Get-PropNames $object)
    foreach ($field in $expected) { if ($actual -notcontains $field) { $errors.Add("$label missing: $field") } }
    foreach ($field in $actual) { if ($expected -notcontains $field) { $errors.Add("$label unexpected: $field") } }
}

function Test-T4Json([string]$raw) {
    $errors = New-Object 'System.Collections.Generic.List[string]'
    $obj = $null
    try { $obj = $raw | ConvertFrom-Json -ErrorAction Stop }
    catch { return [pscustomobject]@{ JsonValid = $false; Passed = $false; ErrorCount = 1; Errors = @('JSON parse: ' + $_.Exception.Message); Object = $null } }
    if ($null -eq $obj -or $obj -is [System.Array] -or $obj -is [string]) {
        return [pscustomobject]@{ JsonValid = $true; Passed = $false; ErrorCount = 1; Errors = @('Top-level JSON value must be an object'); Object = $null }
    }

    $top = @('title','topic','description_summary','hashtags','target_duration_minutes','fact_checks','music_policy','blocks')
    Test-ExactFields $obj $top 'root' $errors

    if (-not ($obj.title -is [string]) -or $obj.title.Length -lt 55 -or $obj.title.Length -gt 70) { $errors.Add('title must be a string of 55-70 characters') }
    if (-not ($obj.topic -is [string]) -or [string]::IsNullOrWhiteSpace($obj.topic)) { $errors.Add('topic must be a non-empty string') }
    if (-not ($obj.description_summary -is [string])) { $errors.Add('description_summary must be a string') }
    elseif (([regex]::Matches($obj.description_summary, '[.!?](\s|$)')).Count -ne 2) { $errors.Add('description_summary should contain exactly two sentences') }
    if ($obj.target_duration_minutes -ne 8) { $errors.Add('target_duration_minutes must equal 8') }
    if ($obj.hashtags -isnot [System.Array] -or @($obj.hashtags).Count -lt 5 -or @($obj.hashtags).Count -gt 8) { $errors.Add('hashtags must be an array of 5-8 strings') }
    else { foreach ($h in $obj.hashtags) { if ($h -isnot [string]) { $errors.Add('hashtags must contain only strings'); break } } }
    if ($obj.music_policy -isnot [string] -or [string]::IsNullOrWhiteSpace($obj.music_policy)) { $errors.Add('music_policy must be a non-empty string') }

    if ($obj.fact_checks -isnot [System.Array]) { $errors.Add('fact_checks must be an array') }
    else {
        $fi = 0
        foreach ($f in $obj.fact_checks) {
            $fi++
            Test-ExactFields $f @('claim','source_url','status') "fact_checks[$fi]" $errors
            if ($f.claim -isnot [string] -or $f.source_url -isnot [string] -or $f.status -ne 'verify_before_publish') { $errors.Add("fact_checks[$fi] invalid field types or status") }
        }
    }

    $expectedKinds = @('hook','section','section','section','section','section','cta')
    if ($obj.blocks -isnot [System.Array] -or @($obj.blocks).Count -ne 7) {
        $errors.Add('blocks must be an array of exactly 7 objects')
    } else {
        $blockFields = @('id','kind','heading','voice_text','slides','broll_keywords')
        $slideFields = @('type','title','body','metric','photo_keyword','items','source')
        $allowedTypes = @('text','metric','comparison','quote','list','bar_chart','progress','photo','split','storyboard')
        for ($i = 0; $i -lt 7; $i++) {
            $b = $obj.blocks[$i]
            $idx = $i + 1
            Test-ExactFields $b $blockFields "blocks[$idx]" $errors
            if ($b.kind -ne $expectedKinds[$i]) { $errors.Add("blocks[$idx] kind must be $($expectedKinds[$i])") }
            $expectedId = 'block_' + ('{0:d2}' -f $idx)
            if ($b.id -ne $expectedId) { $errors.Add("blocks[$idx] id must be $expectedId") }
            foreach ($field in @('heading','voice_text')) { if ($b.$field -isnot [string] -or [string]::IsNullOrWhiteSpace($b.$field)) { $errors.Add("blocks[$idx].$field must be non-empty string") } }
            if ($b.slides -isnot [System.Array] -or @($b.slides).Count -ne 3) { $errors.Add("blocks[$idx].slides must contain exactly 3 objects") }
            else {
                for ($j = 0; $j -lt 3; $j++) {
                    $sl = $b.slides[$j]
                    Test-ExactFields $sl $slideFields "blocks[$idx].slides[$($j+1)]" $errors
                    if ($allowedTypes -notcontains $sl.type) { $errors.Add("blocks[$idx].slides[$($j+1)] has unsupported type") }
                    foreach ($field in @('title','body','metric','photo_keyword','source')) { if ($sl.$field -isnot [string]) { $errors.Add("blocks[$idx].slides[$($j+1)].$field must be a string") } }
                    if ($sl.items -isnot [System.Array]) { $errors.Add("blocks[$idx].slides[$($j+1)].items must be an array") }
                }
            }
            if ($b.broll_keywords -isnot [System.Array] -or @($b.broll_keywords).Count -lt 2 -or @($b.broll_keywords).Count -gt 5) { $errors.Add("blocks[$idx].broll_keywords must contain 2-5 strings") }
            else { foreach ($kw in $b.broll_keywords) { if ($kw -isnot [string]) { $errors.Add("blocks[$idx].broll_keywords must contain only strings"); break } } }
        }
    }

    return [pscustomobject]@{ JsonValid = $true; Passed = ($errors.Count -eq 0); ErrorCount = $errors.Count; Errors = @($errors.ToArray()); Object = $obj }
}

$summary = New-Object System.Collections.Generic.List[object]
foreach ($m in $models) {
    Write-Host "`n=== $($m.Name) / $($m.Model) ===" -ForegroundColor Cyan
    $body = @{
        model = $m.Model
        messages = @(
            @{ role = 'system'; content = $systemPrompt },
            @{ role = 'user'; content = $userPrompt }
        )
        temperature = 0.2
        max_tokens = 6000
    } | ConvertTo-Json -Depth 15

    $requestPath = Join-Path $outDir ($m.Name + '_request.json')
    $responsePath = Join-Path $outDir ($m.Name + '_api_response.json')
    $answerPath = Join-Path $outDir ($m.Name + '_answer.txt')
    $parsedPath = Join-Path $outDir ($m.Name + '_parsed.json')
    $metricsPath = Join-Path $outDir ($m.Name + '_metrics.json')
    [System.IO.File]::WriteAllText($requestPath, $body, (New-Object System.Text.UTF8Encoding($false)))

    $sw = [Diagnostics.Stopwatch]::StartNew()
    try {
        $url = $m.BaseUrl.TrimEnd('/') + '/chat/completions'
        $httpStatus = (& curl.exe -sS --fail-with-body -X POST $url `
            -H "Authorization: Bearer $($m.ApiKey)" `
            -H 'Content-Type: application/json; charset=utf-8' `
            --data-binary "@$requestPath" `
            -o $responsePath -w '%{http_code}') -join ''
        $curlExit = $LASTEXITCODE
        $sw.Stop()
        if ($curlExit -ne 0 -or $httpStatus -notmatch '^2') {
            $errorBody = ''
            if (Test-Path $responsePath) { $errorBody = [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($responsePath)) }
            throw "HTTP/curl failure (exit=$curlExit, status=$httpStatus): $errorBody"
        }
        $apiRaw = [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($responsePath))
        $apiObj = $apiRaw | ConvertFrom-Json -ErrorAction Stop
        $answer = [string]$apiObj.choices[0].message.content
        [System.IO.File]::WriteAllText($answerPath, $answer, (New-Object System.Text.UTF8Encoding($true)))
        $check = Test-T4Json $answer
        if ($check.JsonValid) {
            $jsonOut = $check.Object | ConvertTo-Json -Depth 30
            [System.IO.File]::WriteAllText($parsedPath, $jsonOut, (New-Object System.Text.UTF8Encoding($true)))
        }
        $usage = $apiObj.usage
        $metrics = [pscustomobject]@{
            model_name = $m.Name; provider = $m.Provider; model_or_deployment = $m.Model
            http_status = [int]$httpStatus; latency_seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 3)
            prompt_tokens = $usage.prompt_tokens; completion_tokens = $usage.completion_tokens; total_tokens = $usage.total_tokens
            json_valid = $check.JsonValid; schema_pass = $check.Passed; schema_error_count = $check.ErrorCount; schema_errors = $check.Errors
        }
        $metrics | ConvertTo-Json -Depth 10 | Set-Content -Path $metricsPath -Encoding UTF8
        $summary.Add($metrics)
        Write-Host "HTTP $($metrics.http_status); $($metrics.latency_seconds)s; JSON=$($metrics.json_valid); schema=$($metrics.schema_pass); errors=$($metrics.schema_error_count)"
        if (-not $check.Passed) { foreach ($e in $check.Errors) { Write-Host " - $e" } }
    }
    catch {
        $sw.Stop()
        $msg = $_.Exception.Message
        $metrics = [pscustomobject]@{ model_name = $m.Name; provider = $m.Provider; model_or_deployment = $m.Model; http_status = 'ERROR'; latency_seconds = [Math]::Round($sw.Elapsed.TotalSeconds,3); error = $msg }
        $metrics | ConvertTo-Json -Depth 6 | Set-Content -Path $metricsPath -Encoding UTF8
        $summary.Add($metrics)
        Write-Warning "$($m.Name) failed: $msg"
    }
}

$summaryPath = Join-Path $outDir 'summary.json'
$summary | ConvertTo-Json -Depth 12 | Set-Content -Path $summaryPath -Encoding UTF8
Write-Host "`nT4 completed. Results: $outDir" -ForegroundColor Green
Write-Host 'Check the raw answer files; the parser does not repair Markdown fences or malformed JSON.'
Remove-Variable mwsKey, secure, ptr -ErrorAction SilentlyContinue
