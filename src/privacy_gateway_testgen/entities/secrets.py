"""Synthetic secret and credential factories.

Every credential carries an explicit ``example``/``fake`` marker or a PEM label
that real parsers reject.  None can authenticate against a real system.
"""

from __future__ import annotations

import base64
import random

from ..models import Entity
from . import common


def _api_key(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "api_key", "sk_example_fake_" + common.hexstr(rng, 24))


def _access_token(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "access_token", "at_example_fake_" + common.hexstr(rng, 20))


def _refresh_token(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "refresh_token", "rt_example_fake_" + common.hexstr(rng, 20))


def _oauth_secret(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "oauth_client_secret", "cs_example_fake_" + common.hexstr(rng, 20))


def _jwt(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "jwt_token", common.fake_jwt(rng))


def _password(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "password", f"Example-Fake-Passw0rd-{common.digits(rng, 4)}!")


def _db_credential(rng: random.Random, ctx) -> Entity:
    value = f"example_app:fake_password_{common.hexstr(rng, 8)}"
    return Entity("secrets", "database_credential", value)


def _connection_string(rng: random.Random, ctx) -> Entity:
    value = (
        f"postgresql://example_app:fake_password_{common.hexstr(rng, 8)}"
        f"@db.{ctx.org['slug']}.internal:5432/appdb"
    )
    return Entity("secrets", "connection_string", value)


def _ssh_key(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "ssh_private_key", common.fake_pem(rng, "EXAMPLE FAKE OPENSSH PRIVATE KEY"))


def _tls_key(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "tls_private_key", common.fake_pem(rng, "EXAMPLE FAKE PRIVATE KEY"))


def _cloud_key(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "cloud_access_key", "AKIAFAKEEXAMPLE" + common.digits(rng, 5))


def _cloud_secret(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "cloud_secret_key", "fakeExampleSecret" + common.alnum(rng, 24))


def _service_account(rng: random.Random, ctx) -> Entity:
    value = (
        '{"type":"service_account","project_id":"example-fake-project",'
        '"private_key":"FAKE-EXAMPLE-NOT-A-REAL-KEY"}'
    )
    return Entity("secrets", "service_account_credential", value)


def _webhook_secret(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "webhook_secret", "whsec_example_fake_" + common.hexstr(rng, 20))


def _encryption_key(rng: random.Random, ctx) -> Entity:
    raw = f"EXAMPLE-FAKE-ENCRYPTION-KEY-{common.hexstr(rng, 8)}".encode()
    return Entity("secrets", "encryption_key", base64.b64encode(raw).decode("ascii"))


def _env_var(rng: random.Random, ctx) -> Entity:
    return Entity("secrets", "env_var_secret", f"DB_PASSWORD=example_fake_{common.hexstr(rng, 12)}")


def _config_credential(rng: random.Random, ctx) -> Entity:
    return Entity(
        "secrets",
        "config_credential",
        f"api_key: sk_example_fake_{common.hexstr(rng, 16)}",
    )


GENERATORS = {
    "api_key": (14, _api_key),
    "access_token": (10, _access_token),
    "refresh_token": (6, _refresh_token),
    "oauth_client_secret": (6, _oauth_secret),
    "jwt_token": (7, _jwt),
    "password": (9, _password),
    "database_credential": (7, _db_credential),
    "connection_string": (7, _connection_string),
    "ssh_private_key": (4, _ssh_key),
    "tls_private_key": (3, _tls_key),
    "cloud_access_key": (7, _cloud_key),
    "cloud_secret_key": (5, _cloud_secret),
    "service_account_credential": (4, _service_account),
    "webhook_secret": (5, _webhook_secret),
    "encryption_key": (4, _encryption_key),
    "env_var_secret": (7, _env_var),
    "config_credential": (6, _config_credential),
}
