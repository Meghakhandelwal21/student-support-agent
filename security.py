import re

SECRET_PATTERNS = [
    re.compile(r'(?i)\b(?:my\s+)?password\s*(?:is|:|=)\s*\S+'),
    re.compile(r'(?i)\botp\s*(?:is|:|=)\s*\d{4,8}\b'),
    re.compile(r'(?i)\b(?:api[_ -]?key|access token|secret token)\s*(?:is|:|=)\s*\S+'),
]

def contains_sensitive_secret(text):
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)
