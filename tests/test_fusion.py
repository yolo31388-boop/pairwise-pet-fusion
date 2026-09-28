"""宠物融合与变异系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pet.fusion import FusionSystem, Pet

class TestFusionNotAdditive:
    def test_fusion_not_simple_addition(self):
        fs = FusionSystem(seed=42)
        main = Pet("m1", "main", 50, atk=100)
        material = Pet("mat1", "mat", 50, atk=80)
        result = fs.fuse(main, material)
        assert result.atk < 180  # bug1: 直接相加=180

class TestMutationChance:
    def test_mutation_chance_scales_with_quality(self):
        fs = FusionSystem()
        common = Pet("m1", "m", 1, quality="common")
        legendary = Pet("m2", "m", 1, quality="legendary")
        c1 = fs.get_mutation_chance(common, common)
        c2 = fs.get_mutation_chance(legendary, legendary)
        assert c2 > c1  # bug2: 都是0.1

class TestMaterialConsumed:
    def test_material_pet_consumed(self):
        fs = FusionSystem(seed=42)
        main = Pet("m1", "main", 50, atk=100)
        material = Pet("mat1", "mat", 50, atk=80)
        result = fs.fuse(main, material)
        # 融合后material应该被标记为已消耗或系统有消耗记录
        assert hasattr(fs, "consumed_pets") or material.atk == 0
        # 更严格：同一只副宠不能融合两次

class TestCoreSkillsPreserved:
    def test_core_skills_not_lost(self):
        fs = FusionSystem(seed=1)
        main = Pet("m1", "main", 50, skills=["bite"], core_skills=["immortal"])
        material = Pet("mat1", "mat", 50, skills=["claw"])
        result = fs.fuse(main, material)
        assert "immortal" in result.core_skills or "immortal" in result.skills  # bug4: 可能丢失

class TestLevelBonus:
    def test_material_level_gives_exp_bonus(self):
        fs = FusionSystem()
        main = Pet("m1", "main", 50, atk=100)
        low_mat = Pet("mat1", "mat", 10, atk=80)
        high_mat = Pet("mat2", "mat", 100, atk=80)
        b1 = fs.get_level_bonus(main, low_mat)
        b2 = fs.get_level_bonus(main, high_mat)
        assert b2 > b1  # bug5: 都是0

class TestNegativeMutationWarning:
    def test_negative_mutation_can_be_declined(self):
        fs = FusionSystem(seed=42)
        main = Pet("m1", "main", 50, atk=100)
        material = Pet("mat1", "mat", 50, atk=80)
        # 系统应该有预览功能，显示变异方向
        assert hasattr(fs, "preview_fusion")
        preview = fs.preview_fusion(main, material)
        assert "mutation" in preview or "can_decline" in str(preview)  # bug6: 无预览

class TestFusionCooldown:
    def test_fusion_has_cooldown(self):
        fs = FusionSystem()
        main = Pet("m1", "main", 50, atk=100)
        material = Pet("mat1", "mat", 50, atk=80)
        fs.fusion_cd["m1"] = 100.0
        assert fs.can_fuse(main, material, 50.0) == False  # bug7: 返回True
        assert fs.can_fuse(main, material, 150.0) == True
