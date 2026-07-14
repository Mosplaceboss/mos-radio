$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "..\..\Platform\Core\Get-PlatformConfig.ps1")

function Get-ScheduleFolder {
    try {
        $websiteRoot = Get-MoPlacePlatformPath -Key "website_root"
        if ($websiteRoot) {
            $scheduleDir = Join-Path $websiteRoot "Schedule"
            if (Test-Path -LiteralPath $scheduleDir) {
                return (Resolve-Path -LiteralPath $scheduleDir).Path
            }
        }
    }
    catch {
        Write-Warning "Platform schedule path unavailable: $($_.Exception.Message)"
    }
    return $PSScriptRoot
}

Add-Type -AssemblyName System.Drawing

$folder = Get-ScheduleFolder
$csvFile = "$folder\schedule.csv"
$moImage = "$folder\moschedule.png"

$websiteOutput = "$folder\schedule-today.jpg"

# PASTE YOUR REAL NEOCITIES API KEY BETWEEN THE QUOTES
$neocitiesApiKey = "4482436cf13f825e58a9f5c7722144c6"

$today = Get-Date
$todayName = $today.DayOfWeek.ToString()

Write-Host "Today is $todayName"
Write-Host "Reading schedule from $csvFile"

if (!(Test-Path $csvFile)) {
    Write-Host "ERROR: schedule.csv not found."
    exit
}

$allItems = Import-Csv $csvFile
$items = @($allItems | Where-Object { $_.Day.Trim() -eq $todayName })

if ($items.Count -eq 0) {
    Write-Host "ERROR: No schedule items found for $todayName"
    exit
}

function Draw-CenteredText($g, $text, $font, $brush, $x, $y, $w, $h) {
    $fmt = New-Object System.Drawing.StringFormat
    $fmt.Alignment = "Center"
    $fmt.LineAlignment = "Center"
    $rect = New-Object System.Drawing.RectangleF $x,$y,$w,$h
    $g.DrawString($text, $font, $brush, $rect, $fmt)
}

function Draw-Paw($g, $cx, $cy, $scale, $brush) {
    $g.FillEllipse($brush, ($cx - 14*$scale), ($cy + 5*$scale), (28*$scale), (24*$scale))
    $g.FillEllipse($brush, ($cx - 24*$scale), ($cy - 8*$scale), (13*$scale), (15*$scale))
    $g.FillEllipse($brush, ($cx - 8*$scale), ($cy - 18*$scale), (13*$scale), (15*$scale))
    $g.FillEllipse($brush, ($cx + 8*$scale), ($cy - 18*$scale), (13*$scale), (15*$scale))
    $g.FillEllipse($brush, ($cx + 22*$scale), ($cy - 8*$scale), (13*$scale), (15*$scale))
}

function Draw-Newspaper($g, $x, $y, $scale, $pen, $brush) {
    $w = [int](52 * $scale)
    $h = [int](38 * $scale)
    $rect = New-Object System.Drawing.Rectangle $x,$y,$w,$h
    $g.DrawRectangle($pen, $rect)
    $g.FillRectangle($brush, ($x + 6*$scale), ($y + 7*$scale), (14*$scale), (12*$scale))
    $g.DrawLine($pen, ($x + 25*$scale), ($y + 8*$scale), ($x + 45*$scale), ($y + 8*$scale))
    $g.DrawLine($pen, ($x + 25*$scale), ($y + 16*$scale), ($x + 45*$scale), ($y + 16*$scale))
    $g.DrawLine($pen, ($x + 7*$scale), ($y + 26*$scale), ($x + 45*$scale), ($y + 26*$scale))
    $g.DrawLine($pen, ($x + 7*$scale), ($y + 33*$scale), ($x + 45*$scale), ($y + 33*$scale))
}

function New-ScheduleImage($OutputFile, $Width, $Height, $ScheduleItems, $DayLabel, $ShowNewsBrief, $ShowTodaysDate) {

    if (Test-Path $OutputFile) {
        Remove-Item $OutputFile -Force
    }

    $bmp = New-Object System.Drawing.Bitmap $Width, $Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = "AntiAlias"
    $g.TextRenderingHint = "AntiAliasGridFit"

    $bgRect = New-Object System.Drawing.Rectangle 0,0,$Width,$Height
    $bgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $bgRect,
        [System.Drawing.Color]::FromArgb(5,38,52),
        [System.Drawing.Color]::FromArgb(0,0,0),
        90
    )
    $g.FillRectangle($bgBrush,$bgRect)

    $cyanColor = [System.Drawing.Color]::FromArgb(0,255,220)
    $goldColor = [System.Drawing.Color]::Gold
    $whiteColor = [System.Drawing.Color]::White

    $cyan = New-Object System.Drawing.SolidBrush $cyanColor
    $gold = New-Object System.Drawing.SolidBrush $goldColor
    $white = New-Object System.Drawing.SolidBrush $whiteColor
    $pawBlue = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(0,190,255))
    $newsFill = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(45,255,255,255))

    $borderPen = New-Object System.Drawing.Pen $cyanColor, 6
    $thinPen = New-Object System.Drawing.Pen $cyanColor, 2
    $glowPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(120,0,255,220)), 8

    $g.DrawRectangle($borderPen, 18, 18, $Width - 36, $Height - 36)

    $titleFont = New-Object System.Drawing.Font("Arial", 30, [System.Drawing.FontStyle]::Bold)
    # Use a smaller font for longer day labels so text does not run off the image.
    if ($DayLabel -eq "Monday - Thursday") {
        $sideFont = New-Object System.Drawing.Font("Arial", 30, [System.Drawing.FontStyle]::Bold)
    } else {
        $sideFont = New-Object System.Drawing.Font("Arial", 38, [System.Drawing.FontStyle]::Bold)
    }
    $buttonFont = New-Object System.Drawing.Font("Arial", 29, [System.Drawing.FontStyle]::Bold)
    $newsTitleFont = New-Object System.Drawing.Font("Arial", 27, [System.Drawing.FontStyle]::Bold)
    $newsTimeFont = New-Object System.Drawing.Font("Arial", 21, [System.Drawing.FontStyle]::Bold)

    $circleSize = [int]($Width * 0.29)
    $circleX = [int](($Width - $circleSize) / 2)
    $circleY = 45

    $circleBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(45,0,255,220))
    $g.FillEllipse($circleBrush, $circleX, $circleY, $circleSize, $circleSize)
    $g.DrawEllipse($glowPen, $circleX, $circleY, $circleSize, $circleSize)
    $g.DrawEllipse($borderPen, $circleX, $circleY, $circleSize, $circleSize)

    if (Test-Path $moImage) {
        $img = [System.Drawing.Image]::FromFile($moImage)
        $imgW = [int]($circleSize * 0.96)
        $imgH = $imgW
        $imgX = $circleX + [int](($circleSize - $imgW) / 2)
        $imgY = $circleY + [int](($circleSize - $imgH) / 2)
        $g.DrawImage($img, $imgX, $imgY, $imgW, $imgH)
        $img.Dispose()
    }

    $leftX = 35
    $leftW = 360
    $g.DrawLine($thinPen, $leftX + 20, 165, $leftX + $leftW - 20, 165)
    Draw-CenteredText $g "TODAY ON" $titleFont $white $leftX 205 $leftW 45
    Draw-CenteredText $g "MO'S PLACE" $titleFont $gold $leftX 255 $leftW 45
    Draw-CenteredText $g "RADIO" $titleFont $gold $leftX 305 $leftW 45
    $g.DrawLine($thinPen, $leftX + 20, 390, $leftX + $leftW - 20, 390)

    $rightW = 420
    $rightX = $Width - $rightW - 35
    $g.DrawLine($thinPen, $rightX + 35, 285, $rightX + $rightW - 35, 285)
    Draw-CenteredText $g $DayLabel.ToUpper() $sideFont $cyan $rightX 190 $rightW 85

    # Daily-generated images show today's actual date.
    # This changes every time the script runs.
    if ($ShowTodaysDate) {
        $dateFont = New-Object System.Drawing.Font("Arial", 22, [System.Drawing.FontStyle]::Bold)
        $todayDateText = "TODAY: " + (Get-Date).ToString("MMMM d, yyyy").ToUpper()
        Draw-CenteredText $g $todayDateText $dateFont $white $rightX 315 $rightW 55
        $g.DrawLine($thinPen, $rightX + 35, 405, $rightX + $rightW - 35, 405)
    }

    # Daily News Brief only appears when $ShowNewsBrief is true.
    # It is intentionally lower than the logo circle, leaving clean space below the circle.
    if ($ShowNewsBrief) {
        $newsX = 245
        $newsY = 505
        $newsW = $Width - 490
        $newsH = 82
        $newsRect = New-Object System.Drawing.Rectangle $newsX,$newsY,$newsW,$newsH
        $g.FillRectangle($newsFill, $newsRect)
        $g.DrawRectangle($thinPen, $newsRect)

        Draw-Newspaper $g ($newsX + 28) ($newsY + 22) 1.0 $thinPen $gold
        Draw-Newspaper $g ($newsX + $newsW - 80) ($newsY + 22) 1.0 $thinPen $gold
        Draw-CenteredText $g "DAILY NEWS BRIEF" $newsTitleFont $white $newsX ($newsY + 8) $newsW 34

        # Plain spacing only. No bullet characters and no vertical lines through the times.
        Draw-CenteredText $g "7:15 AM     12:15 PM     5:15 PM" $newsTimeFont $gold $newsX ($newsY + 44) $newsW 28

        $startY = 610
    } else {
        $startY = 520
    }

    $gap = 8
    $x = 55
    $blockWidth = $Width - 110
    $buttonY = $Height - 90
    $availableHeight = $buttonY - 30 - $startY
    $count = @($ScheduleItems).Count
    $blockHeight = [Math]::Floor(($availableHeight - ($gap * ($count - 1))) / $count)
    if ($blockHeight -gt 92) { $blockHeight = 92 }
    if ($blockHeight -lt 52) { $blockHeight = 52 }

    if ($blockHeight -lt 75) {
        $timeFont = New-Object System.Drawing.Font("Arial", 21, [System.Drawing.FontStyle]::Bold)
        $showFont = New-Object System.Drawing.Font("Arial", 23, [System.Drawing.FontStyle]::Bold)
        $descFont = New-Object System.Drawing.Font("Arial", 15, [System.Drawing.FontStyle]::Bold)
        $timeYAdd = 22
        $showYAdd = 8
        $descYAdd = 38
    } else {
        $timeFont = New-Object System.Drawing.Font("Arial", 28, [System.Drawing.FontStyle]::Bold)
        $showFont = New-Object System.Drawing.Font("Arial", 28, [System.Drawing.FontStyle]::Bold)
        $descFont = New-Object System.Drawing.Font("Arial", 20, [System.Drawing.FontStyle]::Bold)
        $timeYAdd = 28
        $showYAdd = 12
        $descYAdd = 50
    }

    foreach ($item in $ScheduleItems) {
        $rect = New-Object System.Drawing.Rectangle $x,$startY,$blockWidth,$blockHeight
        $blockBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(38,255,255,255))

        $g.FillRectangle($blockBrush,$rect)
        $g.DrawRectangle($thinPen,$rect)

        $timeText = "$($item.Start) - $($item.End)"
        $g.DrawString($timeText, $timeFont, $gold, ($x + 55), ($startY + $timeYAdd))

        # Removed the vertical divider line between the time and show columns.
        # It was visually cutting through the AM/PM area on the generated image.

        $g.DrawString($item.Show, $showFont, $white, ($x + 430), ($startY + $showYAdd))
        $g.DrawString($item.Description, $descFont, $cyan, ($x + 430), ($startY + $descYAdd))

        $startY += ($blockHeight + $gap)
    }

    $btnX = 260
    $btnW = $Width - 520
    $btnH = 58

    $btnBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(45,0,80,120))
    $btnRect = New-Object System.Drawing.Rectangle $btnX,$buttonY,$btnW,$btnH
    $g.FillRectangle($btnBrush,$btnRect)
    $g.DrawRectangle($borderPen,$btnRect)

    Draw-Paw $g ($btnX + 65) ($buttonY + 27) 1.05 $pawBlue
    Draw-CenteredText $g "CLICK TO LISTEN LIVE" $buttonFont $white $btnX ($buttonY + 8) $btnW 42
    Draw-Paw $g ($btnX + $btnW - 65) ($buttonY + 27) 1.05 $pawBlue

    $jpgEncoder = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
    $encoderParams = New-Object System.Drawing.Imaging.EncoderParameters(1)
    $encoderParams.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, 88L)
    $bmp.Save($OutputFile, $jpgEncoder, $encoderParams)

    $g.Dispose()
    $bmp.Dispose()

    Write-Host "Created $OutputFile"
}

function Get-DayItems($DayName) {
    return @($allItems | Where-Object { $_.Day.Trim() -eq $DayName })
}

function Is-WeekdayForNews($DayName) {
    return @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday") -contains $DayName
}

# Main website image for today's actual day.
# This image always shows the real day and today's date.
New-ScheduleImage $websiteOutput 1400 1400 $items $todayName (Is-WeekdayForNews $todayName) $true

Write-Host "Local website image updated:"
Write-Host $websiteOutput

if ($neocitiesApiKey -and $neocitiesApiKey -ne "PASTE_YOUR_REAL_KEY_HERE") {

    Write-Host "Uploading schedule-today.jpg to Neocities..."

    $response = curl.exe `
      -H "Authorization: Bearer $neocitiesApiKey" `
      -F "schedule-today.jpg=@$websiteOutput" `
      "https://neocities.org/api/upload"

    Write-Host "Neocities response:"
    Write-Host $response

} else {
    Write-Host "Neocities API key missing. Skipping upload."
}
