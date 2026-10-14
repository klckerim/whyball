# Deploying WhyBall to Azure Container Apps

Written 2026-10-14, main path reworked the same day. One container (API + built UI), region Sweden Central, its **own resource group**
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
export APP_ENV="whyball-env"               # Container Apps environment name
export ACR_NAME="<globally unique, 5-50 lowercase letters and digits>"
export IDENTITY_NAME="whyball-pull"        # user-assigned identity that pulls the image
export IMAGE_TAG="p1-$(date +%Y%m%d-%H%M)" # a new tag for every build; never reuse or use 'latest'

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

**If a later command fails with `AADSTS50158: External security challenge not satisfied`:** Learn's note for
`az containerapp up` is to sign in again with the Graph scope and rerun the command:
```bash
az login --scope https://graph.microsoft.com//.default
```
Source: <https://learn.microsoft.com/azure/container-apps/quickstart-code-to-cloud#build-and-deploy-the-container-app>
(Note under the `up` command). The error means your tenant asks for an extra sign-in challenge (for example an
external MFA provider, via Conditional Access); if it persists, the Entra sign-in log names the policy
(<https://learn.microsoft.com/troubleshoot/azure/azure-container-registry/acr-authentication-errors> is the ACR troubleshooting page).
The same note appears again where `az acr login` is used (3.3).

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

## 3. Main path: local amd64 build, push to ACR, create the app with a user-assigned identity

Why this path: the image is built on your machine (`--platform linux/amd64`, required because Container Apps runs
`linux/amd64` and Apple silicon builds arm64 by default: <https://learn.microsoft.com/azure/container-apps/containers>),
so it does not depend on ACR Tasks (task runs can be paused on credit-based subscriptions, see Appendix A). The app pulls
with a **user-assigned identity** that only holds `AcrPull`; no registry password exists. Learn recommends a user-assigned
identity for image pulls and gives this exact sequence:
<https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull> (Azure CLI tab); the build-and-deploy
quickstart is <https://learn.microsoft.com/azure/container-apps/quickstart-code-to-cloud>.
Run from the repository root (where the `Dockerfile` is).

### 3.1 User-assigned identity ✎

```bash
az identity create --name "$IDENTITY_NAME" --resource-group "$APP_RG"
export IDENTITY_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$APP_RG" --query id --output tsv)
echo "$IDENTITY_ID"
```
Source: <https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull#create-a-user-assigned-managed-identity>
(`az identity create --name --resource-group`; `az identity show … --query id --output tsv`).

Expected: JSON of the identity; `IDENTITY_ID` is `/subscriptions/…/userAssignedIdentities/<name>`. **If not:** empty id means the
create failed: rerun it and read the error (section 1.3 if a provider is unregistered).

### 3.2 Registry and ARM-token check ✎ 💲

```bash
az acr create --resource-group "$APP_RG" --name "$ACR_NAME" --sku Basic
export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)
export ACR_ID=$(az acr show --name "$ACR_NAME" --query id --output tsv)
az acr config authentication-as-arm show -r "$ACR_NAME"
```
If the last command reports the status as disabled, enable it:
```bash
az acr config authentication-as-arm update -r "$ACR_NAME" --status enabled
```
Source: `az acr create --resource-group --name --sku`:
<https://learn.microsoft.com/azure/container-registry/container-registry-get-started-azure-cli#create-a-container-registry>
(that page shows `--sku Standard`; `--sku Basic` is the cheaper tier priced in section 9 and is TODO(verify)). `--query loginServer`
and `--query id` on `az acr show`: TODO(verify). The ARM-token commands are quoted from the image-pull page ("Your Azure Container
Registry must allow ARM audience tokens for authentication in order to use managed identity to pull images"):
<https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull#prerequisites>.

Expected: registry JSON with `"provisioningState": "Succeeded"`; the ARM-token status is enabled (after the update if needed).
**If not:** the name is taken (5-50 lowercase letters and digits, unique in Azure): pick another and reset `ACR_NAME`.

### 3.3 Log in, build, push ✎ 💲

```bash
az acr login --name "$ACR_NAME"
docker build --platform linux/amd64 -t "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG" .
docker push "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG"
```
Source: `az acr login --name`, tag and `docker push <login-server>/<repo>:<tag>`:
<https://learn.microsoft.com/azure/container-registry/container-registry-get-started-azure-cli#log-in-to-registry>;
`--platform linux/amd64`: <https://learn.microsoft.com/azure/container-apps/containers> (Linux `amd64` only).

Expected: `Login Succeeded`; the push ends with a `digest: sha256:...` line. **If not:**
- **`AADSTS50158: External security challenge not satisfied`** during login: run
  `az login --scope https://graph.microsoft.com//.default` and repeat (source: the Learn note quoted in 1.1, written for
  `az containerapp up`; that it also cures `az acr login` is TODO(verify)). If login keeps failing or Docker cannot do it:
  ```bash
  TOKEN=$(az acr login --name "$ACR_NAME" --expose-token --output tsv --query accessToken)
  docker login "$ACR_LOGIN_SERVER" --username 00000000-0000-0000-0000-000000000000 --password-stdin <<< "$TOKEN"
  ```
  Source: <https://learn.microsoft.com/azure/container-registry/container-registry-authentication#use-az-acr-login-without-docker-daemon>
  (the all-zero user name is required there). That token still needs a successful `az login`.
- `unauthorized` on push: the token lasts about 3 hours; rerun `az acr login`.
- `exec format error` later in the console log: the image is arm64; rebuild with `--platform linux/amd64`.
- Docker Hub timeouts while pulling the base images: rerun; they were transient DNS errors.
- `lookup ... no such host` or `i/o timeout` during build or push (seen in a real run): quit Docker Desktop completely
  and start it again. If it persists, add a `"dns"` entry (for example your router or a public resolver) to the Docker
  Engine settings in Docker Desktop and restart; also check the network and any VPN.
- Check that the Docker daemon is running with `docker info 2>&1 | grep "Server Version"`: the client part of
  `docker info` prints even when the server is down, so `docker info | head -3` proves nothing.

### 3.4 Container Apps environment ✎ 💲

```bash
az containerapp env create --name "$APP_ENV" --resource-group "$APP_RG" --location "$LOCATION"
```
Source: <https://learn.microsoft.com/azure/container-apps/get-started-existing-container-image#create-an-environment>

Expected: JSON of the environment (it also creates a Log Analytics workspace). **If not:** provider errors: section 1.3.
- The command can fail on the local network (`OSError 22`, `Connection aborted`) although the environment is created in
  Azure. Before running it again, look:
  ```bash
  az containerapp env show --name "$APP_ENV" --resource-group "$APP_RG" --query properties.provisioningState -o tsv
  ```
  A second `create` makes a second Log Analytics workspace. If the state is `Succeeded`, go on to 3.5.

### 3.5 Create the app with size and replicas 💲

```bash
az containerapp create \
  --name "$APP_NAME" --resource-group "$APP_RG" --environment "$APP_ENV" \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --image "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG" \
  --ingress external --target-port 8000 \
  --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 2 \
  --query properties.configuration.ingress.fqdn --output tsv
```
Source: `--user-assigned`, `--registry-identity`, `--registry-server`, `--image`:
<https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull#create-a-container-app>;
`--ingress external --target-port`, `--cpu`, `--memory`, `--min-replicas`, `--max-replicas`: the `az containerapp create`
reference and its example (`--cpu 0.5 --memory 1.0Gi --min-replicas 4 --max-replicas 8`):
<https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-create>; `--query properties.configuration.ingress.fqdn` on `create`:
<https://learn.microsoft.com/azure/container-apps/get-started-existing-container-image#create-a-container-app>.
0.5 vCPU with 1.0 Gi is a valid Consumption pair:
<https://learn.microsoft.com/azure/container-apps/containers#vcpu-and-memory-allocation-requirements>.
Replica limits (min default 0, max default 10): <https://learn.microsoft.com/azure/container-apps/scale-app#scale-definition>.

**AcrPull is assigned for you.** Learn: "The Azure CLI automatically makes this assignment" (the `acrpull` role for your registry
to the managed identity), in the user-assigned procedure of
<https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull#user-assigned-managed-identity> (only PowerShell
users assign it by hand), and the CLI reference for `--registry-identity` says: "If possible, an 'acrpull' role assignment will
be created for the identity automatically" (<https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-up>). Check it in 3.6.

Expected: after a minute or two, one line with the host name (`<name>.<hash>.swedencentral.azurecontainerapps.io`). Go on to
section 6 and use `--wait 120`. **If not:**
- `ImagePullBackOff` or `unauthorized` in the system log (`az containerapp logs show --name "$APP_NAME" --resource-group "$APP_RG" --type system --tail 50`,
  <https://learn.microsoft.com/azure/container-apps/log-streaming>): see 3.6 (no `AcrPull`) or 3.2 (ARM tokens disabled).
  Role assignments can take a few minutes to take effect.
- `Invalid cpu/memory`: the pair is off the Consumption table (<https://learn.microsoft.com/azure/container-apps/containers#vcpu-and-memory-allocation-requirements>); `--memory` must end in `Gi`.
- Why min 1: no cold start on the first visit. `--min-replicas 0` spends almost nothing while nobody looks (no usage charges
  at zero replicas; the first request then waits for a start).

### 3.6 Verify the pull role and the image 👁

```bash
az role assignment list --scope "$ACR_ID" \
  --query "[].{role:roleDefinitionName, principalId:principalId, scope:scope}" --output table
az identity show --name "$IDENTITY_NAME" --resource-group "$APP_RG" --query principalId --output tsv
```
Source: `az role assignment list --scope`:
<https://learn.microsoft.com/azure/role-based-access-control/role-assignments-list-cli#list-role-assignments-for-a-subscription>
(the same flag, with a registry scope instead of a subscription); the `--query` fields follow that page's example
(`roleDefinitionName`, `scope`); `principalId` on `az identity show`: TODO(verify).

Expected: a row with role `AcrPull` whose `principalId` equals the identity's, at scope = the registry. **If not (no row):** assign it
yourself and recreate nothing else:
```bash
az role assignment create --assignee-object-id "$(az identity show --name "$IDENTITY_NAME" --resource-group "$APP_RG" --query principalId --output tsv)" \
  --assignee-principal-type ServicePrincipal --role "7f951dda-4ed3-4680-a7ca-43fe172d538d" --scope "$ACR_ID"
```
Source: the role id is the `AcrPull` id in the Bicep example of the image-pull page; the command form is
<https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry#manage-role-assignments> (`--assignee-object-id`,
`--assignee-principal-type`, `--role <id>`, `--scope`). Creating a role assignment needs Owner or User Access Administrator.

Optional: what is inside the image (empty output expected; CI runs the same check on every push):
```bash
docker run --rm --user root --entrypoint sh "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG" -c \
  'find / -xdev \( -name ".env" -o -name ".env.*" -o -name notes -o -name .git \) -not -path "/proc/*" -not -path "*/site-packages/*"'
```

## 4. Changing size or replicas later (note)

Size and replicas are already set in 3.5. Only to change them afterwards:
`az containerapp update --name "$APP_NAME" --resource-group "$APP_RG" --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 2`
(Source: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-update>; valid pairs:
<https://learn.microsoft.com/azure/container-apps/containers#vcpu-and-memory-allocation-requirements>).

## 5. Get the URL 👁

```bash
export APP_FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$APP_RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "https://$APP_FQDN"
```
Source: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-show> (`show -n -g`); the
`--query` path is the one Learn uses on `create`: <https://learn.microsoft.com/azure/container-apps/get-started-existing-container-image#create-a-container-app>.

Expected: a host name. **If not:** `az containerapp show -n "$APP_NAME" -g "$APP_RG" -o json` and read `ingress`.

## 6. Smoke test (against the real URL) 👁

```bash
python3 scripts/smoke_remote.py "https://$APP_FQDN"
```
It uses only the standard library and only reads.

**Right after a deploy, add `--wait 120`:** the container runs `python -m app.publish --check` before it
starts the server, and a new revision needs time to become ready, so the first requests can be reset or
refused. `--wait` retries `/healthz` once a second and starts the real checks when it answers (or prints
`FAIL wait: not ready after 120s` if it never does):

```bash
python3 scripts/smoke_remote.py "https://$APP_FQDN" --wait 120
```

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

## 7. Managed identity and the Foundry role: **skip in this version**

**Skip this whole section.** The live container never calls a model (section 10), so it needs no Foundry role. Least privilege: every
extra role is a path to spend or data access that this app does not need, and the repo is public.
The only identity in this deployment is the user-assigned pull identity from 3.1, and it holds `AcrPull` on the
registry only. Do **not** assign Foundry User to anything now: least privilege, and no path to spend on Foundry.

Kept for a future version that adds a request-time model call (not allowed without authentication and a rate limit,
section 10). Then, in this order:

1. Give the app a system-assigned identity ✎: `az containerapp identity assign --name "$APP_NAME" --resource-group "$APP_RG" --system-assigned`
   (Source: <https://learn.microsoft.com/cli/azure/containerapp/identity#az-containerapp-identity-assign>). Its `principalId`:
   `az containerapp identity show --name "$APP_NAME" --resource-group "$APP_RG" --query principalId -o tsv` (field name TODO(verify)).
2. Find the Foundry account id 👁: `az cognitiveservices account show --name "$FOUNDRY_ACCOUNT" --resource-group "$FOUNDRY_RG" --query id -o tsv`
   (Source: <https://learn.microsoft.com/cli/azure/cognitiveservices/account#az-cognitiveservices-account-show>; `--query id` TODO(verify)).
3. Assign **Foundry User** by role id (the name is being renamed; Learn says to use the id) ✎:
   ```bash
   az role assignment create --assignee-object-id "<principalId>" --assignee-principal-type ServicePrincipal \
     --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope "<Foundry account id>"
   ```
   Source: <https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry#manage-role-assignments>.
4. Verify 👁: `az role assignment list --assignee "<principalId>" --all --query "[].{role:roleDefinitionName, scope:scope}" -o table`
   (Source: <https://learn.microsoft.com/azure/role-based-access-control/role-assignments-list-cli#list-role-assignments-for-a-managed-identity>).

The Foundry narrator already uses `DefaultAzureCredential` (`app/explain/credential.py`): locally your `az login`, on
Container Apps a managed identity. With several identities on an app, `DefaultAzureCredential` needs the client id of the
one to use (`managed_identity_client_id`, <https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains#exclude-an-individual-credential>)
or `AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential` (azure-identity 1.24 or later).

## 8. Redeploy, roll back, delete

### 8.1 Redeploy a new version 💲

After the gate (`pytest`, `npm test`, `npm run build`) is green and the change is committed, from the repository root:

```bash
export IMAGE_TAG="p1-$(date +%Y%m%d-%H%M)"
az acr login --name "$ACR_NAME"
docker build --platform linux/amd64 -t "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG" .
docker push "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG"
az containerapp update --name "$APP_NAME" --resource-group "$APP_RG" \
  --image "$ACR_LOGIN_SERVER/$APP_NAME:$IMAGE_TAG"
python3 scripts/smoke_remote.py "https://$APP_FQDN" --wait 120
```
Source: build and push as in 3.3; `az containerapp update --image`:
<https://learn.microsoft.com/azure/container-apps/revisions-manage#updating-your-container-app>. A new image tag
every time (Learn: "Avoid using static tags like `latest`": <https://learn.microsoft.com/azure/container-apps/containers>).
The size and replica settings carry over from the previous revision.

(If you lost the shell variables: `ACR_NAME` from `az acr list --resource-group "$APP_RG" --query "[0].name" -o tsv` (TODO(verify)),
`ACR_LOGIN_SERVER` as in 3.2.)

Expected: a new revision becomes active and the smoke test passes. **If not:** read the console and system log
(section 6), then roll back (8.2).

### 8.2 Roll back 💲

Option A (simplest): update to the previous tag. The tags are in the registry:
```bash
az acr repository show-tags --name "$ACR_NAME" --repository "$APP_NAME" --output table
az containerapp update --name "$APP_NAME" --resource-group "$APP_RG" \
  --image "$ACR_LOGIN_SERVER/$APP_NAME:<PREVIOUS_TAG>"
```
Source: `show-tags`: <https://learn.microsoft.com/azure/container-registry/container-registry-get-started-azure-cli#list-container-images>;
`update --image`: <https://learn.microsoft.com/azure/container-apps/revisions-manage#updating-your-container-app>.
The previous tag stays in the registry, so this is exact.

Option B: route traffic to an older revision (needs multiple-revision mode).
```bash
az containerapp revision list --name "$APP_NAME" --resource-group "$APP_RG" -o table
az containerapp revision set-mode --name "$APP_NAME" --resource-group "$APP_RG" --mode multiple
az containerapp revision activate --revision <OLD_REVISION> --resource-group "$APP_RG"
az containerapp ingress traffic set --name "$APP_NAME" --resource-group "$APP_RG" --revision-weight <OLD_REVISION>=100
```
Source: <https://learn.microsoft.com/azure/container-apps/revisions-manage> (list, set-mode, activate);
<https://learn.microsoft.com/cli/azure/containerapp/ingress/traffic#az-containerapp-ingress-traffic-set>
(`--revision-weight name=weight`). Afterwards `--mode single` again and deactivate the bad revision
(`az containerapp revision deactivate --revision <BAD_REVISION> --resource-group "$APP_RG"`).

Expected after either option: section 6 passes. **If not:** read the console log before trying again.

### 8.3 Delete everything this guide created ✎

Only the **new** group. Never the Foundry group.

```bash
echo "$APP_RG"                       # check this is the app group, not $FOUNDRY_RG
az group delete --name "$APP_RG"     # asks for confirmation
```
Source: <https://learn.microsoft.com/cli/azure/group#az-group-delete> (`--yes` skips the prompt; `--no-wait` returns at once).

Expected: after confirmation, the group (app, environment, workspace, registry, pull identity, and the `AcrPull` assignment, which
lives on the registry inside the same group) is deleted within minutes. The Foundry group is never touched.

**A role assignment is not removed together with an identity that lives elsewhere.** This only matters if you applied section 7
(skipped in this version): that role assignment sits on the Foundry account, outside `$APP_RG`, so deleting the group leaves it
orphaned. Remove it first:
```bash
az role assignment delete --assignee "<principalId>" --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope "<Foundry account id>"
```
Source: <https://learn.microsoft.com/azure/role-based-access-control/role-assignments-remove#azure-cli> (`--assignee`, `--role`, `--scope`;
the page shows role names, the role id form is TODO(verify)). Without section 7 there is nothing to clean up.
**If not:** `az group exists --name "$APP_RG"` (Source: same page as the delete command).

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
  `anthropic` module. The image has no model client; the Azure packages in it come only from the optional
  Application Insights extra (section 13) and are imported only when its connection string is set.
- `app/serve.py` refuses to start if `python -m app.publish --check` fails.

If a later feature needs a request-time model call: put authentication and a rate limit in front of it first,
then change the frozen list on purpose. Do not assign the managed identity a Foundry role before that.

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

## 13. Optional: Application Insights request traces: **skip in this version**

**Skip this whole section.** It is optional; the app is deployed and verified without it, and the image runs without a
connection string (the code does nothing in that case). It is kept for later. Same least-privilege reasoning as section 7: nothing in the live container needs another Azure resource,
role or secret.

Lowest priority; the app works without it. `app/telemetry.py` does **nothing** (no import, no exporter, no
network) unless `APPLICATIONINSIGHTS_CONNECTION_STRING` is set. When it is set, the Microsoft OpenTelemetry
distro (`microsoft-opentelemetry==1.3.9`, released 2026-09-09, the newest release at least two weeks old on
2026-10-14; extra `monitor`, installed in the image) sends **request traces only**: logging and metrics are
switched off in code (`disable_logging`, `disable_metrics`), so no application log text leaves the container.
A request trace has the method, path, status and duration (and the client address that the platform adds);
the app has no user data, login or cookies. Package choice: Learn now recommends this distro for new apps
(<https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=python>), and its keyword
arguments are documented at <https://github.com/microsoft/opentelemetry-distro-python>.
What the HTTP instrumentation records per request beyond that (headers, query strings) is not documented
there: TODO(verify) before relying on "no personal data" for anything beyond this demo's own URLs.

### 13.1 Create the Application Insights resource, backed by the existing workspace 💲

```bash
export LAW_ID=$(az monitor log-analytics workspace list --resource-group "$APP_RG" --query "[0].id" -o tsv)  # TODO(verify)
az monitor app-insights component create --app "$APP_NAME-ai" --location "$LOCATION"   --resource-group "$APP_RG" --workspace "$LAW_ID" --kind web --application-type web
```
Source: <https://learn.microsoft.com/cli/azure/monitor/app-insights/component#az-monitor-app-insights-component-create>
(`--app`, `--location`, `--resource-group`, `--workspace`, `--kind`, `--application-type`; the command comes from the
`application-insights` CLI extension, which installs itself on first use). The `log-analytics workspace list` form is TODO(verify).

Expected: JSON with `"provisioningState": "Succeeded"`. Data goes to the Log Analytics workspace (first 5 GB a month
free, see section 9). **If not:** if the extension prompt appears, accept it; if the workspace id is empty, create
the resource without `--workspace` (Learn shows that form) and note it then has its own retention setting.

### 13.2 Give the connection string to the app as a secret ✎

```bash
export AI_CONNECTION_STRING=$(az monitor app-insights component show --app "$APP_NAME-ai"   --resource-group "$APP_RG" --query connectionString -o tsv)           # TODO(verify) field name
az containerapp secret set --name "$APP_NAME" --resource-group "$APP_RG"   --secrets "ai-connection-string=$AI_CONNECTION_STRING"                # TODO(verify) flags
az containerapp update --name "$APP_NAME" --resource-group "$APP_RG"   --set-env-vars "APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:ai-connection-string"
unset AI_CONNECTION_STRING
```
Source: `show`: <https://learn.microsoft.com/cli/azure/monitor/app-insights/component#az-monitor-app-insights-component-show>;
secrets and `secretref:` in `--env-vars`: <https://learn.microsoft.com/azure/container-apps/manage-secrets#referencing-secrets-in-environment-variables>
and <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-up> (`--env-vars`: "Prefix value with 'secretref:'");
`az containerapp secret set`: <https://learn.microsoft.com/azure/container-apps/containerapp-up#configure-container-app-settings>
(the command is named there; its flags are TODO(verify)). The value lives only in the Container Apps secret store
and your shell variable; it is not in the image or the repo. Changing a secret creates no revision; the `update`
with the env var does, and that is what makes the app pick it up (same Learn page: deploy a new revision or restart one).

Expected: the new revision starts; the console log shows no `telemetry stays off` line. **If not:**
`az containerapp logs show … --type console --tail 50` (section 6). "Exporter is missing a valid region" means the
connection string is wrong (it must contain `IngestionEndpoint=https://<region>…`).

### 13.3 Verify the first request trace 👁

```bash
python3 scripts/smoke_remote.py "https://$APP_FQDN"
```
Then in the portal: the Application Insights resource → **Investigate → Transaction search** (or **Overview →
Server requests**). Source: <https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=python#confirm-data-is-flowing>
("it might take a few minutes for data to show up").

Expected: within a few minutes, requests for `/healthz`, `/api/matches` and the replay appear. **If not:** the
Learn troubleshooting page for Python linked from the same article; first check the secret name matches.

To turn it off: `az containerapp update … --remove-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING` (flag in the
`update` syntax on the CLI reference page). Deleting `$APP_RG` (8.3) removes the resource with everything else.

## Appendix A: optional cloud build (`az containerapp up --source`)

**Not recommended; not the main path.** One command creates the environment, a registry and the app and builds the image in Azure
with ACR Tasks. It is not recommended because ACR Tasks can be unavailable on a new or credit-based subscription: Learn says
"Azure Container Registry task runs are temporarily paused from Azure free credits"
(<https://learn.microsoft.com/azure/container-registry/container-registry-tasks-overview>). It also pulls with a system-assigned
identity (not the one from 3.1) and names its own resources, so do not mix it with section 3 in the same resource group.

```bash
az containerapp up \
  --name "$APP_NAME" --resource-group "$APP_RG" --location "$LOCATION" \
  --source . --ingress external --target-port 8000
az containerapp update --name "$APP_NAME" --resource-group "$APP_RG" \
  --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 2
```
Source: <https://learn.microsoft.com/azure/container-apps/containerapp-up#deploy-from-local-source-code> (creates the resource group,
environment and Log Analytics workspace, a registry, builds with the Dockerfile, pushes, deploys; uses `EXPOSE` for the port);
parameters: <https://learn.microsoft.com/cli/azure/containerapp#az-containerapp-up>; resources and scale after `up`:
<https://learn.microsoft.com/azure/container-apps/containerapp-up#configure-container-app-settings>.
`.dockerignore` keeps `.env*`, `notes/` and `.git` out of the uploaded source.

Redeploy (`--environment` takes a name or resource id):
```bash
az containerapp up --name "$APP_NAME" --resource-group "$APP_RG" --environment "<environment name>" --source .
```
Source: same `containerapp-up` page (redeploy needs `--resource-group` and `--environment`). The environment name:
`az containerapp env list --resource-group "$APP_RG" -o table` (TODO(verify)). Rollback here: Option B in 8.2.

Expected: several minutes of build output, then the app URL. **If not:**
- "waiting for the Cloud Build agent" and then nothing: rerun (Learn names a transient error); add `--debug`.
- `AADSTS50158`: see 1.1.
- The cloud build is refused (task runs paused): use the main path (section 3).
