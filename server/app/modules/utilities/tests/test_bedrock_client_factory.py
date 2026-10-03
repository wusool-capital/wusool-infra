"""`build_bedrock_runtime_client` — the both-or-neither credentials check
and `boto3.client(...)` call that used to be duplicated near-verbatim
across `matching_engine`'s, `enrichment`'s, `discrepancies`', `meetings`'
and `lead_magnets`' own Bedrock clients.
"""

from botocore.config import Config

from app.modules.utilities.providers.bedrock.client_factory import build_bedrock_runtime_client


def test_no_keys_uses_the_default_credential_chain() -> None:
    client = build_bedrock_runtime_client(region_name="eu-central-1")
    assert client.meta.region_name == "eu-central-1"


def test_only_one_key_set_falls_back_to_the_default_credential_chain() -> None:
    """Both-or-neither: passing just one key would make boto3 raise
    PartialCredentialsError instead of falling back to the credential
    provider chain — a partially-set pair must be treated as unset."""
    client = build_bedrock_runtime_client(region_name="eu-central-1", access_key_id="only-one-set")
    assert client.meta.region_name == "eu-central-1"


def test_both_keys_set_are_used_explicitly() -> None:
    client = build_bedrock_runtime_client(
        region_name="eu-central-1",
        access_key_id="AKIATEST",
        secret_access_key="secret",
    )
    credentials = client._request_signer._credentials
    assert credentials.access_key == "AKIATEST"
    assert credentials.secret_key == "secret"


def test_a_module_specific_config_is_applied() -> None:
    config = Config(connect_timeout=10, read_timeout=300)
    client = build_bedrock_runtime_client(region_name="eu-central-1", config=config)
    assert client.meta.config.read_timeout == 300
