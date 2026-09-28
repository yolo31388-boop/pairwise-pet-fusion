"""宠物融合与变异系统 - 含7个bug"""
import random
from dataclasses import dataclass, field

@dataclass
class Pet:
    pid: str
    name: str
    level: int
    atk: float
    skills: list = field(default_factory=list)
    core_skills: list = field(default_factory=list)  # 不可丢失
    quality: str = "common"
    fusion_count: int = 0

class FusionSystem:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.fusion_cd: dict[str, float] = {}  # bug7: 无冷却

    def fuse(self, main: Pet, material: Pet) -> Pet:
        # bug1: 属性直接相加
        result = Pet(f"fused_{self.rng.randint(1000,9999)}", "fused", main.level)
        result.atk = main.atk + material.atk
        # bug2: 变异概率固定
        # bug3: 副宠不消失
        # bug4: 核心技能可能丢失
        all_skills = list(set(main.skills + material.skills))
        result.skills = random.sample(all_skills, min(3, len(all_skills))) if all_skills else []
        result.core_skills = main.core_skills  # 这个保留了，但bug在别处
        result.level = main.level  # bug5: 不考虑副宠等级
        result.fusion_count = main.fusion_count + 1
        return result

    def get_mutation_chance(self, main: Pet, material: Pet) -> float:
        # bug2: 固定概率
        return 0.1

    def can_fuse(self, main: Pet, material: Pet, current_time: float) -> bool:
        # bug7: 无冷却检查
        return True

    def get_level_bonus(self, main: Pet, material: Pet) -> int:
        # bug5: 副宠等级不转化
        return 0
