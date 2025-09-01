param(
    [string]$appName = "M365 Data Agent"
)

if (-not (Get-Module -ListAvailable -Name Microsoft.Graph)) {
    Install-Module -Name Microsoft.Graph -Scope CurrentUser -Force -AllowClobber
}

# Create the Azure AD app registration
$appRegistration = New-AzADApplication -DisplayName $appName

$appIdentifierUri = "api://botid-$($appRegistration.AppId)"
Set-AzADApplication -ApplicationId $appRegistration.AppId -IdentifierUri $appIdentifierUri

# Configure the app's authentication settings for web platform
$appAuthenticationWeb = New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphWebApplication
$appAuthenticationWeb.RedirectUri = @("https://token.botframework.com/.auth/web/redirect") 
$appAuthenticationWeb.ImplicitGrantSetting = @{EnableAccessTokenIssuance='true'; EnableIdTokenIssuance='true'}
$web = $appAuthenticationWeb
Set-AzADApplication -ApplicationId $appRegistration.AppId -Web $web

# create an application secret - to be used by the application for OBO flows
$appCredential = New-AzADAppCredential -ObjectId $appRegistration.Id -EndDate (Get-Date).AddYears(3)

# list to contain scopes for all required apps (M365 graph and Databricks)
$requiredResourceAccess = @()

# add permission to Microsoft Graph
$graphResourceAccess = New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphRequiredResourceAccess
$graphAccessList = @()
$graphAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{
    Id = "37f7f235-527c-4136-accd-4a02d197296e"; Type = "Scope" })) # openid
$graphAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{
    Id = "14dad69e-099b-42c9-810b-d002981feec1"; Type = "Scope" })) # profile
$graphAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{
    Id = "e1fe6dd8-ba31-4d61-89e7-88639da4683d"; Type = "Scope" })) # User.Read
$graphResourceAccess.ResourceAppId = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
$graphResourceAccess.ResourceAccess = $graphAccessList
$requiredResourceAccess += $graphResourceAccess

# app permission for Databricks
$databricksResourceAccess = New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphRequiredResourceAccess
$databricksAccessList = @()
$databricksAccessList += ((New-Object -TypeName Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphResourceAccess -Property @{
     Id = "739272be-e143-11e8-9f32-f2801f1b9fd1"; Type = "Scope" }))
$databricksResourceAccess.ResourceAppId = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d" # Databricks
$databricksResourceAccess.ResourceAccess = $databricksAccessList
$requiredResourceAccess += $databricksResourceAccess
Set-AzADApplication -ApplicationId $appRegistration.AppId -RequiredResourceAccess $requiredResourceAccess

# Expose an API
$permissionScope = New-Object Microsoft.Azure.Powershell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphPermissionScope
$permissionScope.Id = [Guid]::NewGuid()
$permissionScope.AdminConsentDescription = "Allow the app to access the API as the signed-in user."
$permissionScope.AdminConsentDisplayName = "Access API as user"
$permissionScope.UserConsentDescription = "Allow the app to access the API as you."
$permissionScope.UserConsentDisplayName = "Access API as you"
$permissionScope.IsEnabled = $true
$permissionScope.Type = "User"
$permissionScope.Value = "access_as_user"
$api = $appRegistration.Api
$api.Oauth2PermissionScope += $permissionScope
Set-AzADApplication -ApplicationId $appRegistration.AppId -Api $api

# Grant Teams access to API
$preAuthorizedApplications = @()
$permissionScopeTemp = $permissionScope.Id
$preAuthorizedApplications += (New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphPreAuthorizedApplication -Property @{
    AppId = "1fec8e78-bce4-4aaf-ab1b-5451cc387264"; DelegatedPermissionId = @("$($permissionScopeTemp)") # Microsoft Teams Desktop / Mobile client
})
$preAuthorizedApplications += (New-Object Microsoft.Azure.PowerShell.Cmdlets.Resources.MSGraph.Models.ApiV10.MicrosoftGraphPreAuthorizedApplication -Property @{
    AppId = "5e3ce6c0-2b1f-4285-8d4b-75ee78787346"; DelegatedPermissionId = @("$($permissionScopeTemp)") # Microsoft Teams Web client
})

$api.PreAuthorizedApplication= $preAuthorizedApplications
Set-AzADApplication -ApplicationId $appRegistration.AppId -Api $api

# TODO: Grant admin consent for the permissions

# Output the app registration details
Write-Output "App Registration Created:"
Write-Output "  App ID: $($appRegistration.AppId)"
Write-Output "  Display Name: $($appRegistration.DisplayName)"
Write-Output "  Identifier URI: $($appIdentifierUri)"
Write-Output "  Client Secret: $($appCredential.SecretText)"
Write-Output "  App API Scope: $($appIdentifierUri + "/" + "access_as_user")"
$tenantId = (Get-AzContext).Tenant.Id
Write-Output "  Tenant ID: $tenantId"