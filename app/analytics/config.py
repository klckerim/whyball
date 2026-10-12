"""Analytics eşikleri ve ağırlıkları.

Metrik ve moment kodu sayısal eşik içermez; hepsi buradan okunur. Değerler
senaryo beklentileri ve senaryosuz maçlardaki moment sıklığına göre kalibre
edilmiştir (bkz. tests/test_moments.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalyticsConfig:
    # --- saha ---
    pitch_length: float = 105.0
    final_third_x: float = 70.0  # kendi kale çizgisinden uzaklık; ötesi son üçte bir

    # --- baskı endeksi ---
    pressure_window_min: float = 10.0
    w_shot: float = 3.0
    w_entry: float = 1.0
    w_corner: float = 2.0
    min_pressure_volume: float = 6.0  # penceredeki toplam bunun altındaysa denge 0

    # --- baskı kayması (histerezis) ---
    shift_enter: float = 0.5  # |denge| bunu aşınca taraf baskın sayılır
    shift_exit: float = 0.2  # |denge| bunun altına inince nötr
    shift_cooldown_min: float = 8.0
    shift_rearm_min: float = 5.0  # bu kadar nötr kalınırsa baskı sönmüş sayılır, sonraki baskınlık yeni kayma

    # --- üstünlük ama sonuçsuz ---
    dominance_window_min: float = 20.0
    dominance_shot_margin: int = 4
    dominance_possession: float = 0.58
    dominance_cooldown_min: float = 15.0

    # --- önem skoru ---
    importance_base: dict[str, float] = field(
        default_factory=lambda: {
            "goal": 0.6,
            "red_card": 0.55,
            "penalty": 0.5,
            "score_change": 0.7,
            "pressure_shift": 0.35,
            "dominance_without_reward": 0.4,
        }
    )
    late_game_minute: int = 75  # 2. devrede bu dakikadan sonra late_bonus
    late_bonus: float = 0.15
    close_game_bonus: float = 0.1  # olay sonrası fark ≤ close_game_margin ise
    close_game_margin: int = 1
    from_behind_bonus: float = 0.15

    # --- çıktı ---
    max_evidence: int = 10
    summary_decimals: int = 3


DEFAULT_CONFIG = AnalyticsConfig()
