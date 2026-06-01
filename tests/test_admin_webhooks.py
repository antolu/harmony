from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — OPS-02")
@pytest.mark.integration
def test_webhook_delivery() -> None:
    pass


@pytest.mark.skip(reason="not implemented — OPS-02")
@pytest.mark.integration
def test_webhook_retry_on_failure() -> None:
    pass


@pytest.mark.skip(reason="not implemented — OPS-02")
@pytest.mark.integration
def test_webhook_hmac_signature() -> None:
    pass
