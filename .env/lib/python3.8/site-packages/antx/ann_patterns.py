hl = chr(200000)  # hfml local_id lower
hu = chr(1000049)  # hfml local_id upper

HFML_ANN_PATTERN = [
    ("author", fr"(\<[{hl}-{hu}]?au)"),
    ("book-title", fr"(\<[{hl}-{hu}]?k1)"),
    ("poti_title", fr"(\<[{hl}-{hu}]?k2)"),
    ("chapter_title", fr"(\<[{hl}-{hu}]?k3)"),
    ("cittation_start", fr"(\<[{hl}-{hu}]?g)"),
    ("citation_end", r"(g\>)"),
    ("sabche_start", fr"(\<[{hl}-{hu}]?q)"),
    ("sabche_end", r"(q\>)"),
    ("tsawa_start", fr"(\<[{hl}-{hu}]?m)"),
    ("tsawa_end", r"(m\>)"),
    ("yigchung_start", fr"(\<[{hl}-{hu}]?y)"),
    ("yigchung_end", r"(y\>)"),
    ("end-1", r"(\>)"),
]
