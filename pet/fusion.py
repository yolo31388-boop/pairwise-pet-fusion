"""宠物融合与变异系统。"""
import random
from dataclasses import dataclass, field


@dataclass
class Pet:
    pid: str
    name: str
    level: int
    atk: float = 0.0
    skills: list = field(default_factory=list)
    core_skills: list = field(default_factory=list)  # 核心技能，不可丢失/覆盖
    quality: str = "common"
    fusion_count: int = 0
    luck: float = 0.0
    exp: int = 0
    consumed: bool = False
    mutation_info: dict = field(default_factory=dict)


class FusionError(Exception):
    """融合无法进行（冷却中、今日次数用完、副宠已消耗等）。"""


class FusionSystem:
    # 属性转化率：副宠属性按品质比例转化到主宠基础上
    TRANSFER_RATE = {
        "common": 0.10,
        "rare": 0.20,
        "epic": 0.30,
        "legendary": 0.50,
    }
    # 副宠品质对变异概率的加成
    QUALITY_MUTATION_BONUS = {
        "common": 0.0,
        "rare": 0.05,
        "epic": 0.10,
        "legendary": 0.20,
    }
    SKILL_INHERIT_RATE = 0.5
    EXP_PER_LEVEL = 100          # 副宠每级转化给主宠的经验
    EXP_PER_MAIN_LEVEL = 100     # 主宠每级所需经验
    FUSION_COOLDOWN = 30.0       # 冷却时间（秒）
    DAILY_LIMIT = 20             # 每日融合次数上限
    PITY_THRESHOLD = 10          # 保底：连续未变异次数
    POSITIVE_RANGE = (1.10, 1.30)
    NEGATIVE_RANGE = (0.80, 0.90)

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.fusion_cd: dict[str, float] = {}
        self.consumed_pets: set[str] = set()
        self.lineage: list[dict] = []
        self.daily_count: dict[str, int] = {}
        self.daily_date: dict[str, object] = {}
        self.attempts_since_mutation: dict[str, int] = {}
        self._seq = 0

    # ---- bug2: 变异概率受副宠品质、融合次数、幸运值影响，且有保底 ----
    def get_mutation_chance(self, main: Pet, material: Pet) -> float:
        base = 0.10
        quality_bonus = self.QUALITY_MUTATION_BONUS.get(material.quality, 0.0)
        count_bonus = min(main.fusion_count * 0.02, 0.20)
        luck_bonus = min(max(material.luck, 0.0) * 0.01, 0.20)
        chance = base + quality_bonus + count_bonus + luck_bonus
        if self.attempts_since_mutation.get(main.pid, 0) >= self.PITY_THRESHOLD:
            chance = 1.0
        return min(chance, 1.0)

    # ---- bug5: 副宠等级转化为经验给主宠 ----
    def get_level_bonus(self, main: Pet, material: Pet) -> int:
        return max(material.level, 0) * self.EXP_PER_LEVEL

    def _apply_exp(self, pet: Pet, extra_exp: int) -> int:
        gained_levels = 0
        pet.exp += max(extra_exp, 0)
        while pet.exp >= self.EXP_PER_MAIN_LEVEL:
            pet.exp -= self.EXP_PER_MAIN_LEVEL
            pet.level += 1
            gained_levels += 1
        return gained_levels

    # ---- bug7: 冷却时间 + 每日次数限制 ----
    def can_fuse(self, main: Pet, material: Pet, current_time: float = 0.0,
                 day: object = None) -> bool:
        last = self.fusion_cd.get(main.pid)
        if last is not None and current_time - last < self.FUSION_COOLDOWN:
            return False
        if self.daily_date.get(main.pid) != day:
            used = 0
        else:
            used = self.daily_count.get(main.pid, 0)
        if used >= self.DAILY_LIMIT:
            return False
        return bool(main.pid != material.pid and not material.consumed
                    and material.pid not in self.consumed_pets)

    def _require_can_fuse(self, main, material, current_time, day):
        if material.consumed or material.pid in self.consumed_pets:
            raise FusionError("副宠已被消耗，无法再次融合")
        if main.pid == material.pid:
            raise FusionError("主宠不能作为自己的副宠")
        last = self.fusion_cd.get(main.pid)
        if last is not None and current_time - last < self.FUSION_COOLDOWN:
            raise FusionError("融合冷却中，请稍后再试")
        if self.daily_date.get(main.pid) != day:
            used = 0
        else:
            used = self.daily_count.get(main.pid, 0)
        if used >= self.DAILY_LIMIT:
            raise FusionError("今日融合次数已达上限")

    # ---- bug4: 核心技能锁定，副宠技能按概率继承 ----
    def _inherit_skills(self, main_skills, core_skills, material_skills, rng):
        skills = list(main_skills)
        for skill in material_skills:
            if skill in skills or skill in core_skills:
                continue
            if rng.random() < self.SKILL_INHERIT_RATE:
                skills.append(skill)
        return skills

    def _roll_mutation(self, chance, base_atk, rng):
        """返回 (是否变异, 方向, 系数, 变化量, 变异后atk)。"""
        if rng.random() >= chance:
            return False, None, 1.0, 0.0, base_atk
        positive = rng.random() < 0.5
        if positive:
            factor = rng.uniform(*self.POSITIVE_RANGE)
            direction = "positive"
        else:
            factor = rng.uniform(*self.NEGATIVE_RANGE)
            direction = "negative"
        new_atk = round(base_atk * factor, 2)
        delta = round(new_atk - base_atk, 2)
        return True, direction, round(factor, 3), delta, new_atk

    def _simulate(self, main: Pet, material: Pet):
        """用 rng 状态快照推演，预览与实际融合结果一致且不污染随机状态。"""
        state = self.rng.getstate()
        try:
            rate = self.TRANSFER_RATE.get(material.quality, self.TRANSFER_RATE["common"])
            base_atk = round(main.atk + material.atk * rate, 2)
            skills = self._inherit_skills(main.skills, main.core_skills,
                                          material.skills, self.rng)
            chance = self.get_mutation_chance(main, material)
            mutated, direction, factor, delta, mutated_atk = self._roll_mutation(
                chance, base_atk, self.rng)
            return {
                "chance": chance,
                "base_atk": base_atk,
                "result_atk": mutated_atk if mutated else base_atk,
                "skills": skills,
                "mutation": {
                    "occurred": mutated,
                    "direction": direction,
                    "factor": factor,
                    "delta": delta,
                } if mutated else None,
            }
        finally:
            self.rng.setstate(state)

    # ---- bug6: 变异方向正负明确提示，负面变异可放弃 ----
    def preview_fusion(self, main: Pet, material: Pet,
                       current_time: float = 0.0, day: object = None) -> dict:
        sim = self._simulate(main, material)
        mutation = sim["mutation"]
        message = "本次融合不会发生变异。"
        can_decline = False
        if mutation:
            if mutation["direction"] == "positive":
                message = (f"变异预览：正面变异，攻击力 x{mutation['factor']}，"
                           f"变化 {mutation['delta']:+.2f}。")
            else:
                can_decline = True
                message = (f"变异预览：负面变异，攻击力 x{mutation['factor']}，"
                           f"变化 {mutation['delta']:+.2f}，可选择放弃此次变异。")
        return {
            "chance": sim["chance"],
            "base_atk": sim["base_atk"],
            "result_atk": sim["result_atk"],
            "skills": list(sim["skills"]),
            "exp_bonus": self.get_level_bonus(main, material),
            "mutation": mutation,
            "can_decline": can_decline,
            "message": message,
        }

    def fuse(self, main: Pet, material: Pet, current_time: float = 0.0,
             day: object = None, accept_negative: bool = False) -> Pet:
        self._require_can_fuse(main, material, current_time, day)

        sim = self._simulate(main, material)
        self._seq += 1

        result = Pet(
            pid=f"fused_{self._seq}",
            name="fused",
            level=main.level,
            exp=main.exp,
            atk=sim["base_atk"],
            skills=sim["skills"],
            core_skills=list(main.core_skills),
            quality=main.quality,
            fusion_count=main.fusion_count + 1,
            luck=main.luck,
        )

        mutation = sim["mutation"]
        mutated = False
        if mutation:
            if mutation["direction"] == "negative" and not accept_negative:
                result.mutation_info = {
                    "occurred": False,
                    "declined": True,
                    "message": "检测到负面变异，已放弃变异，仅保留融合属性。",
                }
            else:
                result.atk = sim["result_atk"]
                result.mutation_info = {
                    "occurred": True,
                    "direction": mutation["direction"],
                    "factor": mutation["factor"],
                    "delta": mutation["delta"],
                    "message": (
                        f"正面变异：攻击力 x{mutation['factor']}，"
                        f"变化 {mutation['delta']:+.2f}。"
                        if mutation["direction"] == "positive"
                        else f"负面变异：攻击力 x{mutation['factor']}，"
                        f"变化 {mutation['delta']:+.2f}。"
                    ),
                }
                mutated = True

        # ---- bug5: 副宠等级转化为经验加成 ----
        exp_bonus = self.get_level_bonus(main, material)
        gained_levels = self._apply_exp(result, exp_bonus)

        # ---- bug3: 消耗副宠并记录谱系 ----
        material.consumed = True
        self.consumed_pets.add(material.pid)
        self.lineage.append({
            "result_pid": result.pid,
            "main_pid": main.pid,
            "material_pid": material.pid,
            "material_quality": material.quality,
            "mutation": mutation if mutated else None,
            "declined_negative": bool(
                mutation and mutation["direction"] == "negative" and not mutated
            ),
            "exp_bonus": exp_bonus,
            "gained_levels": gained_levels,
            "time": current_time,
        })

        # ---- bug2: 保底计数 ----
        if mutated:
            self.attempts_since_mutation[result.pid] = 0
        else:
            self.attempts_since_mutation[result.pid] = (
                self.attempts_since_mutation.get(main.pid, 0) + 1
            )

        # ---- bug7: 写入冷却与每日计数 ----
        self.fusion_cd[main.pid] = current_time
        if self.daily_date.get(main.pid) != day:
            self.daily_date[main.pid] = day
            self.daily_count[main.pid] = 0
        self.daily_count[main.pid] = self.daily_count.get(main.pid, 0) + 1

        return result
