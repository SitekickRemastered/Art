# Base URL for Wayback Machine API
$waybackApi = "https://web.archive.org/cdx/search/cdx?url=www.ytv.com/gamepad/play/*&output=json&fl=timestamp,original"

# Query Wayback Machine
$response = Invoke-RestMethod -Uri $waybackApi

# Check if results were found
if ($response.Count -gt 1) {
    $response = $response[1..($response.Count - 1)]  # Remove header

    # Create a directory for downloads
    $downloadFolder = "$PSScriptRoot\SWFDownloads"
    if (!(Test-Path $downloadFolder)) {
        New-Item -ItemType Directory -Path $downloadFolder | Out-Null
    }

    # Process each entry
    foreach ($entry in $response) {
        $timestamp = $entry[0]
        $originalUrl = $entry[1]

        # Log the original URL for debugging purposes
        Write-Host "Inspecting URL: $originalUrl"

        # Check if the URL points to a .swf file
        if ($originalUrl -match "/gamepad/play/.*\.swf$") {
            # Append 'oe_' to the timestamp URL to get the correct SWF file
            $waybackUrl = "https://web.archive.org/web/$timestamp" + "oe_/$originalUrl"

            # Extract the folder name (the segment right before 'game.swf')
            $segments = $originalUrl -split '/'
            $folderName = $segments[$segments.Length - 2]  # Get the second-to-last segment (the folder)

            $outputFile = "$downloadFolder\$folderName.swf"

            Write-Host "Downloading SWF file: $waybackUrl"

            try {
                # Download the SWF file
                $response = Invoke-WebRequest -Uri $waybackUrl -Method Get -ErrorAction Stop

                # Check if the file is 0KB or starts with <!DOCTYPE html>
                $content = $response.Content
                if ($content.Length -eq 0) {
                    Write-Host "Skipping 0KB SWF file: $waybackUrl"
                    continue
                }

                # Check if the content starts with an HTML doctype
                if ($content -match "<!DOCTYPE html>") {
                    Write-Host "Skipping HTML file: $waybackUrl"
                    continue
                }

                # Save the SWF file with the folder name as the filename
                $response.Content | Set-Content -Path $outputFile -Force
                Write-Host "Downloaded SWF file: $outputFile"

            } catch {
                Write-Host "Failed to download SWF from $waybackUrl. Error: $_"
            }
        }
    }

    Write-Host "Download complete! SWF files saved in: $downloadFolder"
} else {
    Write-Host "No archived URLs found!"
}
