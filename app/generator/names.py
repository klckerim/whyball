"""Sentetik isim havuzları.

Tüm isimler uydurmadır; gerçek kulüp veya oyuncu adı içermez.
Listelerin sırası determinizm için önemlidir, sıralamayı değiştirmek
aynı seed'in farklı çıktı üretmesine yol açar.
"""

FIRST_NAMES: tuple[str, ...] = (
    "Davel", "Korin", "Tamsel", "Orvik", "Lenzar", "Brisko", "Haldin", "Quenlo",
    "Sarvik", "Telmon", "Iveno", "Rastin", "Ombar", "Feliko", "Zandro", "Kesmir",
    "Ulvan", "Pernat", "Gavrin", "Nolvek", "Edrin", "Torvel", "Alvezo", "Murek",
    "Silvek", "Branto", "Hesko", "Viktal", "Jorvan", "Calden",
)

LAST_NAMES: tuple[str, ...] = (
    "Varnelli", "Okodra", "Brestani", "Muldoro", "Kaspet", "Trelvin", "Hazulov",
    "Dremmet", "Sorkani", "Ilvanto", "Pektoran", "Quessel", "Rundavi", "Ostrevik",
    "Belmaro", "Faskoli", "Gundrel", "Nevaskin", "Tolvaro", "Zerimek", "Arbeni",
    "Cavrel", "Lunsko", "Marvetti", "Drokan", "Pelvisto", "Kurrand", "Selvado",
    "Ymberto", "Hostrav",
)

TEAM_CITIES: tuple[str, ...] = (
    "Kelvara", "Morvane", "Tessdal", "Ulmbrook", "Qarsen", "Vellorin",
    "Drunmark", "Isteven", "Halvren", "Zoryk", "Brannoch", "Ostmere",
)

TEAM_SUFFIXES: tuple[str, ...] = (
    "FC", "Athletic", "Rovers", "United", "Spor", "Wanderers",
)
