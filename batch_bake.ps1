
param(
    [Parameter(Mandatory)][string]$InputDir,
    [Parameter(Mandatory)][string]$OutputDir,
    [string]$BlendFile = ".\conversion.blend",
    [string]$Script    = ".\Conversion_Script.py",
    [string]$Blender   = "blender",
    [string]$Texconv = "texconv"
    )
    
$env:MAGICK_OCL_DEVICE = "true"

$TempDir = Join-Path $OutputDir "temp"

Get-ChildItem -Path $InputDir -Recurse -Filter "*.dds" | ForEach-Object {
    $relative  = $_.FullName.Substring($InputDir.Length).TrimStart('\')
    $outFile   = Join-Path $OutputDir ($relative -replace '\.dds$', '.dds')
    $tempDiff  = Join-Path $TempDir ($relative -replace '\.dds$', '_diff.png')
    $tempAlpha = Join-Path $TempDir ($relative -replace '\.dds$', '_alpha.png')
    $tempMerged   = Join-Path $TempDir ($relative -replace '\.dds$', '_merged.png')
    $tempMergedDds = Join-Path $TempDir ($relative -replace '\.dds$', '_merged.dds')
    $inputPng  = Join-Path $TempDir ($relative -replace '\.dds$', '_src.png')

    # Create output and temp dirs
    New-Item -ItemType Directory -Force -Path (Split-Path $outFile)  | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $tempDiff) | Out-Null

    Write-Host "Processing: $relative"

    # Convert source DDS to PNG for Blender
    magick $_.FullName $inputPng

    # Bake
    & $Blender --background --factory-startup $BlendFile --python $Script -- $inputPng $tempDiff $tempAlpha

    # Merge diff and alpha into final PNG
    Write-Host "Merging: $tempDiff, $tempAlpha -> $tempMerged"
    magick $tempDiff `( $tempAlpha -colorspace gray `) -compose CopyOpacity -composite $tempMerged

    Write-Host "Compressing: $tempMerged -> $outFile"
    & $Texconv -f BC7_UNORM -bc x -m 1 -y -nologo -o (Split-Path $tempMergedDds) $tempMerged
    
    if (Test-Path $outFile) { Remove-Item $outFile }
    Move-Item $tempMergedDds $outFile -Force
    
}


# Clean up temp dir
Remove-Item $TempDir -Recurse -ErrorAction SilentlyContinue

Write-Host "Done."
