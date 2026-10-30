from security import contains_sensitive_secret

def test_detect_password():
    assert contains_sensitive_secret("my password is hello123")

def test_detect_otp():
    assert contains_sensitive_secret("OTP: 123456")

def test_safe_text():
    assert not contains_sensitive_secret("Please explain scholarship policy")
