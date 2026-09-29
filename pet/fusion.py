"""宠物融合与变异系统"""
import random
from dataclasses import dataclass, field

# 副宠属性转化率（按品质）
QUALITY_CONVERT_RATE = {
    "common": 0.20,
    "uncommon": 0.25,
    "rare": 0.30,
    "epic": 0.40,
    "legendary": 0.50,
}
# 副宠品质对变异概率的加成
QUALITY_MUTATION_BONUS = {
    "common": 0.00,
    "uncommon": 0.05,
    "rare": 0.10,
    "epic": 0.20,
    "legendary": 0.35,
}

BASE_MUTATION_CHANCE = 0.10
FUSION_COUNT_BONUS = 0.02      # 每次融合历史 +2%
LUCK_BONUS_PER_POINT = 0.001   # 每点幸运值 +0.1%
PITY_THRESHOLD = 10            # 保底：融合次数达到即必定变异
SKILL_INHERIT_CHANCE = 0.5     # 副宠每个技能继承概率
FUSION_COOLDOWN = 30.0         # 融合冷却（秒）
DAILY_FUSION_LIMIT = 10        # 每日融合次数上限
NEGATIVE_MUTATION_RATE = 0.3   # 变异为负面的概率
MUTATION_ATK_RATIO = 0.1       # 变异属性变化幅度（按主宠攻击比例）


@dataclass
class Pet:
    pid: str
    name: str
    level: int
    atk: float = 0.0
    skills: list = field(default_factory=list)
    core_skills: list = field(default_factory=list)  # 不可丢失
    quality: str = "common"
    fusion_count: int = 0
    luck: int = 0


class FusionSystem:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.fusion_cd: dict[str, float] = {}       # 主宠pid -> 上次融合时间
        self.consumed_pets: list[str] = []          # 已消耗副宠pid
        self.lineage: dict[str, dict] = {}          # 融合谱系：结果pid -> 亲代信息
        self.daily_counts: dict[tuple[int, str], int] = {}  # (天, 主宠pid) -> 次数
        self.last_mutation: dict | None = None      # 最近一次变异信息

    # ---- bug1: 属性按主宠为基础 + 副宠按比例转化 ----
    def convert_atk(self, main: Pet, material: Pet) -> float:
        rate = QUALITY_CONVERT_RATE.get(material.quality, QUALITY_CONVERT_RATE["common"])
        return main.atk + material.atk * rate

    # ---- bug2: 变异概率受品质/融合次数/幸运值影响，含保底 ----
    def get_mutation_chance(self, main: Pet, material: Pet) -> float:
        if main.fusion_count + 1 >= PITY_THRESHOLD:
            return 1.0  # 保底变异
        chance = BASE_MUTATION_CHANCE
        chance += QUALITY_MUTATION_BONUS.get(material.quality, 0.0)
        chance += main.fusion_count * FUSION_COUNT_BONUS
        chance += main.luck * LUCK_BONUS_PER_POINT
        return min(chance, 1.0)

    # ---- bug5: 副宠等级转化为经验加成 ----
    def get_level_bonus(self, main: Pet, material: Pet) -> int:
        return material.level // 10

    # ---- bug7: 冷却 + 每日次数限制 ----
    def can_fuse(self, main: Pet, material: Pet, current_time: float) -> bool:
        last = self.fusion_cd.get(main.pid)
        if last is not None and current_time < last + FUSION_COOLDOWN:
            return False
        day = int(current_time // 86400)
        if self.daily_counts.get((day, main.pid), 0) >= DAILY_FUSION_LIMIT:
            return False
        if material.pid in self.consumed_pets:
            return False
        return True

    # ---- bug6: 变异预览，显示方向与属性变化，负面可放弃 ----
    def preview_fusion(self, main: Pet, material: Pet) -> dict:
        chance = self.get_mutation_chance(main, material)
        delta = main.atk * MUTATION_ATK_RATIO
        return {
            "atk": self.convert_atk(main, material),
            "level": main.level + self.get_level_bonus(main, material),
            "mutation": {
                "chance": chance,
                "guaranteed": chance >= 1.0,
                "positive": {"atk": +delta},
                "negative": {"atk": -delta},
                "negative_rate": NEGATIVE_MUTATION_RATE,
            },
            "can_decline": True,  # 负面变异可选择放弃
        }

    def fuse(self, main: Pet, material: Pet, current_time: float | None = None,
             accept_negative_mutation: bool = False) -> Pet:
        # bug3: 副宠只能被消耗一次
        if material.pid in self.consumed_pets:
            raise ValueError(f"副宠 {material.pid} 已被消耗，不能重复融合")
        # bug7: 提供时间时强制冷却/每日限制检查
        if current_time is not None:
            if not self.can_fuse(main, material, current_time):
                raise ValueError("融合冷却中或已达每日次数上限")
            self.fusion_cd[main.pid] = current_time
            day = int(current_time // 86400)
            key = (day, main.pid)
            self.daily_counts[key] = self.daily_counts.get(key, 0) + 1

        result = Pet(f"fused_{self.rng.randint(1000, 9999)}", "fused", main.level)

        # bug1: 主宠为基础 + 副宠按比例转化
        result.atk = self.convert_atk(main, material)

        # bug4: 核心技能锁定，副宠技能按概率继承
        inherited = [s for s in material.skills
                     if s not in main.skills and self.rng.random() < SKILL_INHERIT_CHANCE]
        normal_skills = [s for s in main.skills if s not in main.core_skills]
        result.core_skills = list(main.core_skills)
        result.skills = list(main.core_skills) + normal_skills + inherited

        # bug5: 副宠等级转化为经验，给主宠等级加成
        result.level = main.level + self.get_level_bonus(main, material)

        result.fusion_count = main.fusion_count + 1
        result.quality = main.quality
        result.luck = main.luck

        # bug2/bug6: 变异有方向，负面变异可放弃
        self.last_mutation = None
        if self.rng.random() < self.get_mutation_chance(main, material):
            positive = self.rng.random() >= NEGATIVE_MUTATION_RATE
            delta = main.atk * MUTATION_ATK_RATIO
            if not positive and not accept_negative_mutation:
                self.last_mutation = {
                    "direction": "negative", "declined": True,
                    "changes": {"atk": -delta},
                }
            else:
                result.atk += delta if positive else -delta
                self.last_mutation = {
                    "direction": "positive" if positive else "negative",
                    "declined": False,
                    "changes": {"atk": delta if positive else -delta},
                }

        # bug3: 消耗副宠并记录谱系
        self.consumed_pets.append(material.pid)
        self.lineage[result.pid] = {
            "main": main.pid,
            "material": material.pid,
            "fusion_count": result.fusion_count,
        }
        return result
