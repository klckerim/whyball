# Deploying WhyBall to Azure Container Apps

Written 2026-10-14. One container (API + built UI), region Sweden Central, its **own resource group**
(separate from the Foundry resource group, so deleting the app never touches Foundry).

How to read this file
- This repo is public. Every real value (subscription, tenant, principal ids, resource group names, user
  names) is a shell variable that you export **in your own terminal only**. Never paste real values into a
  file in this repo.
- Each command has a `Source:` line (Microsoft Learn or the Azure Retail Prices API, read 2026-10-14).
  `TODO(verify)` marks anything not confirmed against a Learn page. Run `az <group> <command> --help`
  before trusting a `TODO(verify)` line.
- Every step has **Expected** (what success looks like) and **If not** (what to do).
- Commands that spend money or change Azure are marked 💲 or ✎. Read-only commands are marked 👁.

## 0. Variables

```bash
export SUBSCRIPTION_ID="<your subscription id>"
export LOCATION="swedencentral"
export FOUNDRY_RG="<resource group that holds the Foundry account>"      # only read, never modified
export FOUNDRY_ACCOUNT="<name of the Foundry (AIServices) account>"
export APP_RG="<NEW resource group, used only by WhyBall>"
export APP_NAME="whyball"                  # lowercase letters, digits, '-'; under 32 chars
export IMAGE_TAG="p1-$(date +%Y%m%d-%H%M)" # only used by Plan B
```

## 1. Prerequisites (once per subscription)

### 1.1 Sign in and pick the subscription ✎

```bash
az login
az account set --subscription "$SUBSCRIPTION_ID"
```
Source: <https://learn.microsoft.com/azure/container-apps/containerapp-up#set-up-your-azure-cli-environment>
(`az login`); `az account set`: TODO(verify) (<https://learn.microsoft.com/cli/azure/account#az-account-set>).

Expected: a browser sign-in, then no output (or the subscription JSON). **If not:** `az account show -o table`
to see which subscription is active.

### 1.2 Container Apps CLI extension ✎

```bash
az extension add --name containerapp --upgrade
```
Source: <https://learn.microsoft.com/azure/container-apps/containerapp-up#set-up-your-azure-cli-environment>

Expected: the extension installs (or is already up to date). **If not:** `az extension list -o table`; update
the Azure CLI itself (`az upgrade`, TODO(verify)).

### 1.3 Resource provider registrations ✎

A new subscription may not have these providers registered.

```bash
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.ContainerRegistry
```
Source: Microsoft.App and Microsoft.OperationalInsights:
<https://learn.microsoft.com/azure/container-apps/containerapp-up#set-up-your-azure-cli-environment>;
the command itself: <https://learn.microsoft.com/azure/azure-resource-manager/management/resource-providers-and-types#azure-cli>.
`Microsoft.ContainerRegistry`: TODO(verify): the `containerapp up` page does not list it, but `up` creates a
container registry; registering it is harmless and needed on subscriptions where it is off.

Check (👁):
```bash
az provider show --namespace Microsoft.App --query registrationState -o tsv
az provider show --namespace Microsoft.OperationalInsights --query registrationState -o tsv
az provider show --namespace Microsoft.ContainerRegistry --query registrationState -o tsv
```
Source: <https://learn.microsoft.com/azure/azure-resource-manager/management/resource-providers-and-types#azure-cli>
(`az provider show --namespace`); the `--query registrationState` path is TODO(verify) (the page's sample
output spells the field `registrationsState`; the real field is `registrationState`).

Expected: `Registering` for a minute or two, then `Registered`. Wait until all three say `Registered`.
**If not:** you need Contributor or Owner on the subscription (registering needs `/register/action`, same page).

### 1.4 Confirm the 25 USD budget alert already exists 👁

Portal: **Cost Management + Billing → Cost Management → Budgets** (pick the subscription scope).
Do not create another one.

CLI (preview command group):
```bash
az consumption budget list --query "[].{name:name, amount:amount, grain:timeGrain}" -o table
```
Source: <https://learn.microsoft.com/cli/azure/consumption/budget#az-consumption-budget-list> (the group is
marked Preview; the `--query` field names are TODO(verify)).

Expected: one budget with amount 25. **If not:** use the portal path; if there is no budget, stop and ask
before deploying (the cost estimate in section 9 assumes the alert exists).

## 2. Resource group for the app ✎

```bash
az group create --name "$APP_RG" --location "$LOCATION"
```
Source: <https://learn.microsoft.com/cli/azure/group#az-group-create>

Expected: JSON with `"provisioningState": "Succeeded"`. **If not:** the name is taken or the location is
invalid: `az account list-locations -o table`.

## 3. Build and deploy 💲

Run from the repository root (where the `Dockerfile` is).

```bash
az containerapp up \
  --name "$APP_NAME" \
  --resource-group "$APP_RG" \
  --location "$LOCATION" \
  --source . \
  --ingress external \
  --target-port 8000
```
Source: <https://learn.microsoft.com/azure/container-apps/containerapp-up#deploy-from-local-source-code>;
parameters: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-up>.
It creates the Container Apps environment and Log Analytics workspace (if none exists in the group), creates
an Azure Container Registry, builds the image **in Azure** from the `Dockerfile`, pushes it, and creates the
app. `.dockerignore` keeps `.env*`, `notes/`, `.git` out of the upload.

Expected: several minutes of build output, then a line with the app URL (`https://<name>.<hash>.swedencentral.azurecontainerapps.io`).
**If not:**
- "waiting for the Cloud Build agent" and then nothing: run the same command again (Learn names a transient
  error); add `--debug` for detail (same page).
- The cloud build is refused (ACR Tasks can be restricted on new or trial subscriptions; Learn says ACR task
  runs are "temporarily paused from Azure free credits": <https://learn.microsoft.com/azure/container-registry/container-registry-tasks-overview>):
  use **Plan B** (section 11).
- Provider errors: go back to 1.3.

### 3.1 Image contents check 👁 (optional, local)

```bash
docker build -t whyball:check .
docker run --rm --user root --entrypoint sh whyball:check -c \
  'find / -xdev \( -name ".env" -o -name ".env.*" -o -name notes -o -name .git \) -not -path "/proc/*" -not -path "*/site-packages/*"'
```
Expected: no output. CI runs the same check on every push (`docker` job in `.github/workflows/ci.yml`).

## 4. Size and replicas ✎ 💲

```bash
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$APP_RG" \
  --cpu 0.5 --memory 1.0Gi \
  --min-replicas 1 --max-replicas 2
```
Source: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-update> (the page's own example is
`--cpu 0.5 --memory 1.0Gi --min-replicas 4 --max-replicas 8`). 0.5 vCPU with 1.0 Gi is a valid Consumption
combination: <https://learn.microsoft.com/azure/container-apps/containers#vcpu-and-memory-allocation-requirements>.
Replica limits (min default 0, max default 10): <https://learn.microsoft.com/azure/container-apps/scale-app#scale-definition>.

Expected: JSON of the updated app; a new revision is created. **If not:** `Invalid cpu/memory` means the pair
is off the table above; `--memory` must end in `Gi`.

Why min 1: the first visit is not delayed by a cold start. To spend almost nothing when nobody is looking,
set `--min-replicas 0` instead (Learn: no usage charges at zero replicas; the first request then waits for a start).

## 5. Get the URL 👁

```bash
export APP_FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$APP_RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "https://$APP_FQDN"
```
Source: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-show> (`show -n -g`); the
`--query` path is TODO(verify) (ARM property path, also named in the Learn "connect-apps" FQDN page).

Expected: a host name. **If not:** `az containerapp show -n "$APP_NAME" -g "$APP_RG" -o json` and read `ingress`.

## 6. Smoke test (against the real URL) 👁

```bash
python3 scripts/smoke_remote.py "https://$APP_FQDN"
```
It uses only the standard library and only reads.

Expected:
```
PASS healthz: HTTP 200 {"ok":true,"matches":3}
PASS matches: HTTP 200, 3 matches (expected 3)
PASS deep-link: HTTP 200 text/html; charset=utf-8 /match/<id>
PASS sse-events: 8 of 8 events
PASS sse-progressive: first event after 0.xxs, event 8 after ~2.0s (spread ~2.0s, expected about 2.00s)
PASS total-time: N.Ns
ALL PASSED
```
**If not:**
- `sse-progressive` FAIL with a spread near 0: something between you and the container buffers the stream.
  The app already sends `Cache-Control: no-cache` and `X-Accel-Buffering: no`. Check with `curl -N` and report it.
- `healthz` FAIL / timeout right after deploy: the replica may still be starting; wait a minute and rerun.
- Container exits at start: `az containerapp logs show --name "$APP_NAME" --resource-group "$APP_RG" --type console --tail 50`
  (Source: <https://learn.microsoft.com/azure/container-apps/log-streaming>). The line
  `startup check failed: the publication store is out of date` means `python -m app.publish --check` failed:
  the checkout is inconsistent (see `docs/DEMO_NARRATION.md`); fix it in git and redeploy.

## 7. Managed identity and the Foundry role (optional for this build)

**The current image never calls a model** (see the security note, section 10). The role below is only needed
if a future change makes the container call Foundry. Skipping it is the least-privilege choice. If you
want it in place now:

### 7.1 System-assigned identity ✎

```bash
az containerapp identity assign --name "$APP_NAME" --resource-group "$APP_RG" --system-assigned
```
Source: <https://learn.microsoft.com/cli/azure/containerapp/identity#az-containerapp-identity-assign>

Expected: JSON with `"type": "SystemAssigned"` and a `principalId`. **If not:** `identity show` (below).

```bash
export APP_PRINCIPAL_ID=$(az containerapp identity show --name "$APP_NAME" --resource-group "$APP_RG" \
  --query principalId -o tsv)
```
Source: `identity show`: <https://learn.microsoft.com/cli/azure/containerapp/identity#az-containerapp-identity-show>;
the `principalId` field in its output is TODO(verify).

### 7.2 Find the Foundry account's resource id 👁

```bash
export FOUNDRY_ACCOUNT_ID=$(az cognitiveservices account show \
  --name "$FOUNDRY_ACCOUNT" --resource-group "$FOUNDRY_RG" --query id -o tsv)
```
Source: <https://learn.microsoft.com/cli/azure/cognitiveservices/account#az-cognitiveservices-account-show>
(`--name`, `--resource-group`); `--query id` is TODO(verify) (ARM resource id).

Expected: `/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/<name>`. **If not:** the account
may be listed under a different group: `az cognitiveservices account list -o table`.

### 7.3 Assign **Foundry User** by role id ✎

The role is *Foundry User* (formerly *Azure AI User*). Microsoft says to use the id, not the name, because
the rename is still rolling out: id `53ca6127-db72-4b80-b1b0-d745d6d5456d`.

```bash
az role assignment create \
  --assignee-object-id "$APP_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
  --scope "$FOUNDRY_ACCOUNT_ID"
```
Source: <https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry#manage-role-assignments>
(the Azure CLI tab: role id list and the `--assignee-object-id` / `--assignee-principal-type` form);
account-scope guidance for inference: same site, "Authentication and Authorization in Foundry".
Creating a role assignment needs Owner or User Access Administrator on that scope.

Expected: JSON with `"roleDefinitionId"` ending in the id and your `scope`. **If not:**
`AuthorizationFailed` means you lack permission to assign roles on the Foundry account: ask its owner.

### 7.4 Verify 👁

```bash
az role assignment list --assignee "$APP_PRINCIPAL_ID" --all \
  --query "[].{role:roleDefinitionName, scope:scope}" -o table
```
Source: <https://learn.microsoft.com/azure/role-based-access-control/role-assignments-list-cli#list-role-assignments-for-a-managed-identity>

Expected: one row, role `Foundry User` (or `Azure AI User` while the rename rolls out), scope = the Foundry
account id. **If not:** wait a few minutes (assignments propagate) and rerun.

Credentials in code: the Foundry narrator uses `DefaultAzureCredential` (`app/explain/credential.py`). Locally
it finds your `az login`; on Container Apps it finds this managed identity. To pin it in production set
`AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential` (Source:
<https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains#use-a-specific-credential>;
needs azure-identity 1.24 or later). No key or secret is in the image or the repo.

## 8. Redeploy, roll back, delete

### 8.1 Redeploy a new version 💲

From the repository root, after the gate (`pytest`, `npm test`, `npm run build`) is green and the change is committed:

```bash
export APP_ENV_ID=$(az containerapp show --name "$APP_NAME" --resource-group "$APP_RG" \
  --query properties.environmentId -o tsv)      # TODO(verify) query path
az containerapp up \
  --name "$APP_NAME" \
  --resource-group "$APP_RG" \
  --environment "$APP_ENV_ID" \
  --source .
```
Source: <https://learn.microsoft.com/azure/container-apps/containerapp-up#deploy-from-local-source-code>
(redeploy needs `--resource-group` and `--environment`; `--environment` accepts a name or resource id:
<https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-up>).
`up` does not change the CPU/replica settings, but check with section 4 after a redeploy (`az containerapp show … --query properties.template.scale`, TODO(verify)).
Then run section 6 again.

### 8.2 Roll back 💲

Option A (always works): redeploy a previous image tag.
```bash
export ACR_NAME=$(az acr list --resource-group "$APP_RG" --query "[0].name" -o tsv)   # TODO(verify)
az acr repository show-tags --name "$ACR_NAME" --repository "$APP_NAME" --output table
az containerapp update --name "$APP_NAME" --resource-group "$APP_RG" \
  --image "$ACR_NAME.azurecr.io/$APP_NAME:<PREVIOUS_TAG>"
```
Source: `show-tags`: <https://learn.microsoft.com/azure/container-registry/container-registry-get-started-azure-cli#list-container-images>;
`update --image`: <https://learn.microsoft.com/azure/container-apps/revisions-manage#updating-your-container-app>.
The repository name that `up --source` uses is TODO(verify); `az acr repository list --name "$ACR_NAME"` shows it.
If the registry has a DNL hash the login server differs (`az acr show --query loginServer`, TODO(verify)).

Option B: route traffic to an older revision (needs multiple-revision mode).
```bash
az containerapp revision list --name "$APP_NAME" --resource-group "$APP_RG" -o table
az containerapp revision set-mode --name "$APP_NAME" --resource-group "$APP_RG" --mode multiple
az containerapp revision activate --revision <OLD_REVISION> --resource-group "$APP_RG"
az containerapp ingress traffic set --name "$APP_NAME" --resource-group "$APP_RG" --revision-weight <OLD_REVISION>=100
```
Source: <https://learn.microsoft.com/azure/container-apps/revisions-manage> (list, set-mode, activate);
<https://learn.microsoft.com/cli/azure/containerapp/ingress/traffic#az-containerapp-ingress-traffic-set>
(`--revision-weight name=weight`). Return to single mode afterwards
(`--mode single`) and deactivate the bad revision (`az containerapp revision deactivate --revision … --resource-group …`).

Expected after either option: section 6 passes. **If not:** read the console log (section 6) before trying again.

### 8.3 Delete everything this guide created ✎

Only the **new** group. Never the Foundry group.

```bash
echo "$APP_RG"                       # check this is the app group, not $FOUNDRY_RG
az group delete --name "$APP_RG"     # asks for confirmation
```
Source: <https://learn.microsoft.com/cli/azure/group#az-group-delete> (`--yes` skips the prompt; `--no-wait` returns at once).

Expected: after confirmation, the group (app, environment, workspace, registry) is deleted within minutes. The
role assignment on the Foundry account (7.3) is removed with the identity; verify with 7.4 (no rows).
**If not:** `az group exists --name "$APP_RG"` (Source: same page).

## 9. Cost

Prices: Azure Retail Prices API, region `swedencentral`, USD, read 2026-10-14
(<https://prices.azure.com/api/retail/prices?$filter=serviceName eq 'Azure Container Apps' and armRegionName eq 'swedencentral'>;
same API for `Container Registry` and `Log Analytics`). Consumption plan, one replica, 0.5 vCPU, 1 GiB, 30-day month = 2,592,000 s.

| Meter (per second) | Price |
|---|---|
| vCPU, active | 0.000024 |
| vCPU, idle | 0.000003 |
| Memory per GiB, active and idle | 0.000003 |

Arithmetic (grants ignored, so these are slightly high):
- Memory: 1 GiB × 2,592,000 s × 0.000003 = **7.78**
- vCPU all idle: 0.5 × 2,592,000 × 0.000003 = 3.89 → total **11.66**
- vCPU 5 % active: active 0.5 × 129,600 × 0.000024 = 1.56; idle 0.5 × 2,462,400 × 0.000003 = 3.69 → total **13.02**
- vCPU always active (worst case): 0.5 × 2,592,000 × 0.000024 = 31.10 → total **38.88**
- Container Registry Basic: 0.1666 per day × 30 = **5.00**; stored image ≈ 0.26 GB × 0.1 per GB-month ≈ 0.03.
- Log Analytics: the first 5 GB per month is free (tier read from the price list: 0 USD up to 5 GB, then 2.99 per GB;
  the free amount is an inference from the tier, TODO(verify)). This app logs little.
- Requests: 0.4 per million (negligible here).
- Free monthly grants per subscription (180,000 vCPU-s, 360,000 GiB-s, 2 M requests; Source:
  <https://azure.microsoft.com/pricing/details/container-apps/>) lower the bill by up to about 1.6 to 5.4 USD; not subtracted above.

**Estimate with `--min-replicas 1`: about 17 to 18 USD a month at low traffic (11.7 to 13.0 + 5.0), at most about 44 USD
if the replica were busy all month.** With `--min-replicas 0` the compute part drops to the active seconds only.
The existing 25 USD budget alert fires only in the unlikely busy case; look at it anyway.

Weekly check (5 minutes, every Monday while it is live): Portal → **Cost Management → Cost analysis**, scope = the
`$APP_RG` resource group, view "Accumulated cost", group by **Resource**. Anything other than the app, environment,
workspace and registry is unexpected: investigate. CLI alternative: TODO(verify).

## 10. Security note: no request-time spend

The live service is public and has no login. **No endpoint calls an LLM or any other billable Azure resource
while serving a request.** Every endpoint reads the stored, seeded demo data under `data/`. The model only ran
offline (`eval.llm_run`, `app.publish`), and its output is committed. So a stranger who hammers the URL can
only consume this container's CPU, which is capped at 2 replicas.

This is enforced by tests:
- `tests/test_api_surface.py` freezes the full list of routes (all `GET`) and fails when one is added;
  it also checks that building and serving the app imports no `openai`, `agent_framework`, `azure` or
  `anthropic` module. The image does not install those packages either.
- `app/serve.py` refuses to start if `python -m app.publish --check` fails.

If a later feature needs a request-time model call: put authentication and a rate limit in front of it first,
then change the frozen list on purpose. Do not assign the managed identity a Foundry role before that.

## 11. Plan B: build locally, push to the registry

Use this when the cloud build in section 3 is refused. It needs Docker on your machine.

```bash
export ACR_NAME="<globally unique, 5-50 lowercase letters and digits>"
az acr create --resource-group "$APP_RG" --name "$ACR_NAME" --sku Basic        # 💲 ~0.17/day
az acr login --name "$ACR_NAME"
export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)   # TODO(verify)
docker build --platform linux/amd64 -t "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG" .
docker push "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG"
```
Source: `az acr create`, `az acr login`, tag and push:
<https://learn.microsoft.com/azure/container-registry/container-registry-get-started-azure-cli>
(that page shows `--sku Standard`; Basic is the cheaper tier and fits, see the price list above; its `--sku` value
is TODO(verify)). Container Apps needs `linux/amd64` images:
<https://learn.microsoft.com/azure/container-apps/containers> (a Mac with Apple silicon builds arm64 by default,
so `--platform linux/amd64` is required).

Create the app from the pushed image with the app's own identity pulling from the registry:
```bash
az containerapp up \
  --name "$APP_NAME" --resource-group "$APP_RG" --location "$LOCATION" \
  --image "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG" \
  --registry-server "$ACR_LOGIN_SERVER" --registry-identity system \
  --ingress external --target-port 8000
```
Source: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-up> (`--image`, `--registry-server`,
`--registry-identity system`: "If possible, an 'acrpull' role assignment will be created for the identity
automatically"). Whether this works in one step for a brand-new app: TODO(verify). If the pull fails, assign
`AcrPull` on the registry to the app identity (7.1 for the id, then `az role assignment create --role AcrPull
--assignee-object-id … --assignee-principal-type ServicePrincipal --scope <registry id>`), which Learn requires
for managed-identity pulls: <https://learn.microsoft.com/azure/container-apps/containers#managed-identity-with-azure-container-registry>.

Then continue at section 4. To redeploy in Plan B: build with a new `IMAGE_TAG`, push, and run
`az containerapp update --name "$APP_NAME" --resource-group "$APP_RG" --image "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG"`.

Expected: `docker push` ends with a digest line; the app URL answers section 6. **If not:**
`unauthorized` on push: rerun `az acr login`; `exec format error` in the console log: the image was built for
arm64, rebuild with `--platform linux/amd64`.

## 12. Server-sent events and the ingress timeout

Container Apps HTTP ingress lists "Request time out is 240 seconds"
(<https://learn.microsoft.com/azure/container-apps/ingress-overview#http>). Whether that limit cuts a
streaming response that keeps sending events is TODO(verify); plan as if it does.

- `GET /api/matches/{id}/replay?speed=S` lasts about `match_seconds / S` wall seconds. A 90-minute match is
  about 5,400 match seconds, so it needs `speed >= 23` to finish inside 240 s. The smoke test uses `speed=30`
  and reads 8 events (about 2 s).
- The web UI does not depend on this stream: it plays the fetched `/events` with a client clock
  (`docs/DESIGN.md` D14). Only outside consumers (the planned `/overlay`) use SSE.
- When a connection drops, the client reconnects with `from_t=<t of the last event it received>`; the
  endpoint restarts from that second (events at exactly `from_t` repeat, so de-duplicate on `seq`).
