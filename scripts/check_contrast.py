def lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


pairs = [
    ("body", "#1E2938", "#E7E5E4"),
    ("muted-cand", "#3F4753", "#E7E5E4"),
    ("primary-btn", "#FFFFFF", "#006666"),
    ("primary-ink-on-tint", "#006666", "#D9E9E9"),
    ("nav-current", "#006666", "#D9E9E9"),
    ("pill-good", "#0B5C26", "#D2F0DA"),
    ("pill-warned", "#5C3D05", "#FCEFC0"),
    ("pill-probation", "#7C2D12", "#FDE3C8"),
    ("pill-suspended", "#A3133C", "#FBDCE4"),
    ("pill-banned", "#FFFFFF", "#8F1030"),
    ("pill-expelled", "#FFFFFF", "#6E0B24"),
    ("focus-ring", "#006666", "#E7E5E4"),
    ("placeholder", "#5B6470", "#FFFFFF"),
    ("input-on-white", "#1E2938", "#FFFFFF"),
    ("banner-text", "#1E2938", "#D9E9E9"),
]
ok = True
for name, fg, bg in pairs:
    r = ratio(fg, bg)
    mark = "PASS" if r >= 4.5 else "FAIL"
    if r < 4.5:
        ok = False
    print("%s %-22s %s on %s = %.2f" % (mark, name, fg, bg, r))
print("ALL-AA" if ok else "NEEDS-WORK")
