"""Credential for the Foundry narrator: DefaultAzureCredential.

Locally it falls through to `az login` (AzureCliCredential); on Azure Container Apps it finds the app's
managed identity. To narrow the chain, set AZURE_TOKEN_CREDENTIALS (for example ManagedIdentityCredential).
https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains
"""

from __future__ import annotations

from typing import Any

from .llm_narrator import INSTALL_HINT


def make_credential() -> Any:
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as e:
        raise ImportError(INSTALL_HINT) from e
    return DefaultAzureCredential()
