param(
    [string]$appName = "M365 Data Agent"
)

# Connect to Azure AD using the currently signed-in user (local environment)
# Connect-AzAccount

# Create the Azure AD app registration
$appRegistration = New-AzADApplication -DisplayName $appName
$appRegistration.IdentifierUri = "api://botid-$($appRegistration.AppId)"

$appAuthenticationWeb = New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphWebApplication
$appAuthenticationWeb.RedirectUri = @("https://token.botframework.com/.auth/web/redirect") 
$appAuthenticationWeb.ImplicitGrantSetting = @{EnableAccessTokenIssuance='true'; EnableIdTokenIssuance='true'}
$web = $appAuthenticationWeb
Set-AzADApplication -ApplicationId $appRegistration.AppId -Web $web

# create an application secret - to be used by the application for OBO flows
$appCredential = New-AzADAppCredential -ObjectId $appRegistration.Id -EndDate (Get-Date).AddYears(3)

# add permission to Microsoft Graph
$resourceAccessList = New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphRequiredResourceAccess

$graphAccessList = @()
# openid
$graphAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{ Id = "37f7f235-527c-4136-accd-4a02d197296e"; Type = "Scope" }))
# profile
$graphAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{ Id = "14dad69e-099b-42c9-810b-d002981feec1"; Type = "Scope" }))
# User.Read
$graphAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{ Id = "e1fe6dd8-ba31-4d61-89e7-88639da4683d"; Type = "Scope" }))

$resourceAccessList.ResourceAppId = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
$resourceAccessList.ResourceAccess = $graphAccessList

# apply permissions to the app registration
Set-AzADApplication -ApplicationId $appRegistration.AppId -RequiredResourceAccess $resourceAccessList

# app permission for Databricks access
$databricksPermissions = New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphRequiredResourceAccess
$databricksAccessList = @()
$databricksAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{ Id = "739272be-e143-11e8-9f32-f2801f1b9fd1"; Type = "Scope" }))
$databricksPermissions.ResourceAppId = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d" # Databricks
$databricksPermissions.ResourceAccess = $databricksAccessList


$requiredResourceAccess += $databricksPermissions

# Expose an API
$permissionScope = New-Object Microsoft.Azure.Powershell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphPermissionScope
$permissionScope.Id = [Guid]::NewGuid()
$permissionScope.AdminConsentDescription = "Allow the app to access the API as the signed-in user."
$permissionScope.AdminConsentDisplayName = "Access API as user"
$permissionScope.UserConsentDescription = "Allow the app to access the API as you."
$permissionScope.UserConsentDisplayName = "Access API as you"
$permissionScope.IsEnabled = $true
$permissionScope.Type = "User"
$api = $appRegistration.Api
$api.Oauth2PermissionScope = $permissionScope

# Update the app registration with the new permissions
Set-AzADApplication -ApplicationId $appRegistration.AppId \ 
    -IdentifierUri $appRegistration.IdentifierUri \
    -Authentication $appAuthentication \
    -Api $api

# TODO: Grant admin consent for the permissions
<#
$requiredResourceAccess | ForEach-Object {
    $resourceId = $_.ResourceAppId
    $scope = $_.ResourceAccess | ForEach-Object { $_.Scope }
    New-AzADServiceAppRoleAssignment -ObjectId $appRegistration.AppId -PrincipalId $appRegistration.AppId -ResourceId $resourceId -Scope $scope
}
#>

# Output the app registration details
Write-Output "App Registration Created:"
Write-Output "  App ID: $($appRegistration.AppId)"
Write-Output "  Display Name: $($appRegistration.DisplayName)"
Write-Output "  Identifier URI: $($appRegistration.IdentifierUri)"
Write-Output "  Client Secret: $($appCredential.SecretText)"