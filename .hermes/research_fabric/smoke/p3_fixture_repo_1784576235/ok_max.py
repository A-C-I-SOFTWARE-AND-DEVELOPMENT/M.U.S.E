def safe_max(xs, default=None):
    if not xs:
        return default
    return max(xs)
