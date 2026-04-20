import pytest

from app.services.auth import hash_password, verify_password


def test_hash_password_returns_argon2_string() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert len(hashed) > 50


def test_verify_password_correct() -> None:
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) is True


def test_verify_password_incorrect() -> None:
    hashed = hash_password("secret")
    assert verify_password("wrong", hashed) is False


def test_verify_password_none_hash_returns_false() -> None:
    assert verify_password("any", None) is False


@pytest.mark.parametrize("pw", ["", "  ", "\n"])
def test_hash_password_rejects_blank(pw: str) -> None:
    with pytest.raises(ValueError):
        hash_password(pw)
