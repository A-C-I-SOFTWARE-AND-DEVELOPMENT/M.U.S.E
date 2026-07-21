def flatten(nested):
    out = []
    for sub in nested:
        out.extend(sub)
    return out
