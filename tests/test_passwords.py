from app.passwords import hash_password, normalize_email, validate_password, verify_password


def test_hash_and_verify_round_trip():
    stored = hash_password("correct horse battery")
    assert stored.startswith("scrypt$")
    assert "correct horse" not in stored
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong horse battery", stored)


def test_each_hash_uses_a_fresh_salt():
    assert hash_password("same password here") != hash_password("same password here")


def test_unknown_account_or_garbage_hash_never_verifies():
    assert verify_password("anything at all", None) is False
    assert verify_password("anything at all", "") is False
    assert verify_password("anything at all", "not-a-hash") is False
    assert verify_password("anything at all", "md5$1$2$3$4$5") is False


def test_email_normalisation():
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
    for bad in ["", "plain", "a@b", "two words@example.com", "@example.com", "a" * 250 + "@example.com"]:
        assert normalize_email(bad) is None, bad


def test_password_rules():
    assert validate_password("short") is not None
    assert validate_password("x" * 129) is not None
    assert validate_password("1234567890") is not None
    assert validate_password("ada@example.com", "ada@example.com") is not None
    assert validate_password("a long passphrase works", "ada@example.com") is None