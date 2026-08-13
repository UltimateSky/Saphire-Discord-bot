# Query Railway GraphQL API for project status and trigger redeploy
param (
    [string]$Token
)

if (-not $Token) {
    Write-Host "Please provide -Token <RailwayToken>"
    exit 1
}

$PROJECT_ID = "772f896a-4a6d-4b51-b4ec-595feb330648"
$API = "https://backboard.railway.com/graphql/v2"
$headers = @{
    "Authorization" = "Bearer $Token"
    "Content-Type"  = "application/json"
}

function Invoke-Railway($query, $variables = @{}) {
    $body = @{ query = $query; variables = $variables } | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Uri $API -Method Post -Headers $headers -Body $body
}

Write-Host "Fetching project services and domains..."
$q = @"
query {
  project(id: "$PROJECT_ID") {
    name
    services {
      edges {
        node {
          id
          name
          serviceInstances {
            edges {
              node {
                id
                environmentId
                domains {
                  serviceDomains {
                    domain
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"@

$res = Invoke-Railway $q
Write-Host ($res | ConvertTo-Json -Depth 10)
