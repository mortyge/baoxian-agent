"""Offline Chinese answers for common insurance policy questions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyAnswer:
    answer: str
    source: str


FAQS = (
    (("摩托车", "motorcycle"), PolicyAnswer(
        "摩托车保单（MOTO-001）提供责任险、碰撞险、综合险、医疗费用险，以及无保险/保额不足驾驶人保障。综合险覆盖盗窃、破坏、火灾、天气、坠落物和动物碰撞；还可选配改装件与装备保障、道路救援。具体限额和免赔额需以投保批单为准。",
        "motorcycle_policy.md",
    )),
    (("盗窃", "被盗", "theft"), PolicyAnswer(
        "车辆盗窃属于综合险承保范围，包括整车或零部件被盗，但要适用综合险免赔额和保单限额。综合汽车保单还列明了破坏、火灾、天气损坏等其他综合险风险。",
        "comprehensive_auto_policy.md",
    )),
    (("商业", "责任险限额", "liability limits"), PolicyAnswer(
        "商业汽车保单（COMM-AUTO-001）为商业运营车辆提供第三方人身伤害和财产损失责任险，并支持高于个人车险的责任限额。每人、每次事故的人身伤害限额，以及每次事故财产损失限额，应以该保单的责任限额页和批单为准。",
        "commercial_auto_policy.md",
    )),
    (("高价值", "改装", "aftermarket", "custom"), PolicyAnswer(
        "高价值车辆保单（HV-AUTO-001）可覆盖专业改装车辆、定制车辆和售后配件，但通常要求提前申报、专业评估和相应批单。符合条件时可使用约定价值、OEM 配件和定制修复服务，最终以承保批单及估值材料为准。",
        "high_value_vehicle_policy.md",
    )),
    (("责任险", "不承保", "liability only"), PolicyAnswer(
        "责任险汽车保单（LIAB-AUTO-001）只保障被保险人对第三方造成的人身伤害和财产损失，不保障被保险车辆自身的碰撞、盗窃、破坏、自然灾害、机械故障或改装设备损失，也不保障被保险人及乘客自身伤害。",
        "liability_only_policy.md",
    )),
)


def answer_policy_question(prompt: str) -> PolicyAnswer | None:
    normalized = prompt.casefold()
    for keywords, answer in FAQS:
        if any(keyword.casefold() in normalized for keyword in keywords):
            return answer
    return None
