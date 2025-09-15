param(
    [string]$groupName = "M365 Data Agent Users"
)

# Check if the group already exists
$existingGroup = Get-AzADGroup -Filter "displayName eq '$groupName'"
if ($existingGroup) {
    Write-Host "Group '$groupName' already exists."
    Write-Host "Group ID: $($existingGroup.Id)"
} else {
    # Create the group
    $newGroup = New-AzADGroup -DisplayName $groupName -SecurityEnabled -MailNickname ($groupName -replace ' ', '').ToLower()
    Write-Host "Group '$groupName' created successfully."
    Write-Host "Group ID: $($newGroup.Id)"
}