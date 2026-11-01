"""Released Voucher Adventure offers and question templates."""

from copy import deepcopy
import hashlib


CONTENT_VERSION = "v1"
SUPPORTED_CONTENT_VERSIONS = {"v1"}
UNRELEASED_CONTENT_VERSIONS = set()
VOUCHER_VALUE_CENTS = 4000


BASE_OFFER_DEFINITIONS = [
    {
        "vendor_id": "v_va_001",
        "npc_id": "npc_va_001",
        "vendor_name": "Pepper Bun Vendor",
        "offer_id": "pepper_bun",
        "offer_type": "SECOND_ITEM_PERCENT",
        "root_node_id": "n_va_v1_greet",
        "offer_node_id": "n_va_v1_offer",
        "ask_option_id": "o_va_v1_ask_offer",
        "confirm_option_id": "o_va_v1_confirm_offer",
        "label_en": "Second item half price",
        "label_han": "第二個半價",
        "bundle_size": 2,
        "parameters": {"second_item_rate": 0.5},
        "variants": {
            "A": {"base": 800, "status": "APPROVED", "approved": True},
            "B": {"base": 1000, "status": "APPROVED", "approved": True},
            "C": {"base": 1200, "status": "APPROVED", "approved": True},
        },
        "transfer_variant": {"A": "B", "B": "C", "C": "A"},
        "greet": {
            "A": (
                "Fresh pepper buns are $8 each.",
                "新鮮的胡椒餅，一個八箍。",
                "Sin-chhiⁿ ê hô͘-chio-piáⁿ, chi̍t ê peh kho͘.",
            ),
            "B": (
                "Fresh pepper buns are $10 each.",
                "新鮮的胡椒餅，一個十箍。",
                "Sin-chhiⁿ ê hô͘-chio-piáⁿ, chi̍t ê cha̍p kho͘.",
            ),
            "C": (
                "Fresh pepper buns are $12 each.",
                "新鮮的胡椒餅，一個十二箍。",
                "Sin-chhiⁿ ê hô͘-chio-piáⁿ, chi̍t ê cha̍p-jī kho͘.",
            ),
        },
        "offer_dialogue": (
            "Yeah—the second one is half price.",
            "有，第二個半價。",
            "Ū, tē-jī ê pòaⁿ-kè.",
        ),
    },
    {
        "vendor_id": "v_va_002",
        "npc_id": "npc_va_002",
        "vendor_name": "Chicken Wing Rice Roll Vendor",
        "offer_id": "chicken_wing_rice_roll",
        "offer_type": "PERCENT_OFF",
        "root_node_id": "n_va_v2_greet",
        "offer_node_id": "n_va_v2_offer",
        "ask_option_id": "o_va_v2_ask_offer",
        "confirm_option_id": "o_va_v2_confirm_offer",
        "label_en": "20% off",
        "label_han": "減兩成",
        "bundle_size": 1,
        "parameters": {"discount_rate": 0.2},
        "variants": {
            "A": {"base": 1000, "status": "APPROVED", "approved": True},
            "B": {"base": 2000, "status": "APPROVED", "approved": True},
            "C": {"base": 3000, "status": "APPROVED", "approved": True},
        },
        "transfer_variant": {"A": "B", "B": "C", "C": "A"},
        "greet": {
            "A": (
                "Chicken wing rice rolls are normally $10 each.",
                "雞翅包飯原價一個十箍。",
                "Ke-si̍t pau-pn̄g goân-kè chi̍t ê cha̍p kho͘.",
            ),
            "B": (
                "Chicken wing rice rolls are normally $20 each.",
                "雞翅包飯原價一個二十箍。",
                "Ke-si̍t pau-pn̄g goân-kè chi̍t ê jī-cha̍p kho͘.",
            ),
            "C": (
                "Chicken wing rice rolls are normally $30 each.",
                "雞翅包飯原價一個三十箍。",
                "Ke-si̍t pau-pn̄g goân-kè chi̍t ê saⁿ-cha̍p kho͘.",
            ),
        },
        "offer_dialogue": (
            "They're 20% off today.",
            "今仔日減兩成。",
            "Kin-á-ji̍t kiám nn̄g-siâⁿ.",
        ),
    },
    {
        "vendor_id": "v_va_003",
        "npc_id": "npc_va_003",
        "vendor_name": "Hsinchu Pork Ball Vendor",
        "offer_id": "hsinchu_pork_ball",
        "offer_type": "PERCENT_OFF",
        "root_node_id": "n_va_v3_greet",
        "offer_node_id": "n_va_v3_offer",
        "ask_option_id": "o_va_v3_ask_offer",
        "confirm_option_id": "o_va_v3_confirm_offer",
        "label_en": "30% off",
        "label_han": "減三成",
        "bundle_size": 1,
        "parameters": {"discount_rate": 0.3},
        "variants": {
            "A": {"base": 1000, "status": "APPROVED", "approved": True},
            "B": {"base": 2000, "status": "APPROVED", "approved": True},
            "C": {"base": 3000, "status": "APPROVED", "approved": True},
        },
        "transfer_variant": {"A": "B", "B": "C", "C": "A"},
        "greet": {
            "A": (
                "Hsinchu pork balls are normally $10 each.",
                "新竹貢丸原價一個十箍。",
                "Sin-tek kòng-oân goân-kè chi̍t ê cha̍p kho͘.",
            ),
            "B": (
                "Hsinchu pork balls are normally $20 each.",
                "新竹貢丸原價一個二十箍。",
                "Sin-tek kòng-oân goân-kè chi̍t ê jī-cha̍p kho͘.",
            ),
            "C": (
                "Hsinchu pork balls are normally $30 each.",
                "新竹貢丸原價一個三十箍。",
                "Sin-tek kòng-oân goân-kè chi̍t ê saⁿ-cha̍p kho͘.",
            ),
        },
        "offer_dialogue": (
            "They're 30% off today.",
            "今仔日減三成。",
            "Kin-á-ji̍t kiám saⁿ-siâⁿ.",
        ),
    },
    {
        "vendor_id": "v_va_004",
        "npc_id": "npc_va_004",
        "vendor_name": "Tube Rice Pudding Vendor",
        "offer_id": "tube_rice_pudding",
        "offer_type": "BUY_X_GET_Y",
        "root_node_id": "n_va_v4_greet",
        "offer_node_id": "n_va_v4_offer",
        "ask_option_id": "o_va_v4_ask_offer",
        "confirm_option_id": "o_va_v4_confirm_offer",
        "label_en": "Buy one, get one free",
        "label_han": "買一個送一個",
        "bundle_size": 2,
        "parameters": {"buy_quantity": 1, "free_quantity": 1},
        "variants": {
            "A": {"base": 600, "status": "APPROVED", "approved": True},
            "B": {"base": 800, "status": "APPROVED", "approved": True},
            "C": {"base": 1000, "status": "APPROVED", "approved": True},
        },
        "transfer_variant": {"A": "B", "B": "C", "C": "A"},
        "greet": {
            "A": (
                "Tube rice puddings are $6 each.",
                "筒仔米糕一個六箍。",
                "Tâng-á-bí-ko chi̍t ê la̍k kho͘.",
            ),
            "B": (
                "Tube rice puddings are $8 each.",
                "筒仔米糕一個八箍。",
                "Tâng-á-bí-ko chi̍t ê peh kho͘.",
            ),
            "C": (
                "Tube rice puddings are $10 each.",
                "筒仔米糕一個十箍。",
                "Tâng-á-bí-ko chi̍t ê cha̍p kho͘.",
            ),
        },
        "offer_dialogue": (
            "Yeah—buy one, get one free.",
            "有，買一個送一個。",
            "Ū, bé chi̍t ê sàng chi̍t ê.",
        ),
    },
    {
        "vendor_id": "v_va_005",
        "npc_id": "npc_va_005",
        "vendor_name": "Steamed Taro Cake Vendor",
        "offer_id": "steamed_taro_cake",
        "offer_type": "FIXED_AMOUNT_OFF",
        "root_node_id": "n_va_v5_greet",
        "offer_node_id": "n_va_v5_offer",
        "ask_option_id": "o_va_v5_ask_offer",
        "confirm_option_id": "o_va_v5_confirm_offer",
        "label_en": "$2 off",
        "label_han": "一個減兩箍",
        "bundle_size": 1,
        "parameters": {"amount_off_cents": 200},
        "variants": {
            "A": {"base": 500, "status": "APPROVED", "approved": True},
            "B": {"base": 700, "status": "APPROVED", "approved": True},
            "C": {"base": 900, "status": "APPROVED", "approved": True},
        },
        "transfer_variant": {"A": "C", "B": "C", "C": "A"},
        "greet": {
            "A": (
                "Steamed taro cakes are $5 each.",
                "芋粿巧一個五箍。",
                "Ō͘-kóe-khiáu chi̍t ê gō͘ kho͘.",
            ),
            "B": (
                "Steamed taro cakes are $7 each.",
                "芋粿巧一個七箍。",
                "Ō͘-kóe-khiáu chi̍t ê chhit kho͘.",
            ),
            "C": (
                "Steamed taro cakes are $9 each.",
                "芋粿巧一個九箍。",
                "Ō͘-kóe-khiáu chi̍t ê káu kho͘.",
            ),
        },
        "offer_dialogue": (
            "Today they're $2 off each.",
            "今仔日一個減兩箍。",
            "Kin-á-ji̍t chi̍t ê kiám nn̄g kho͘.",
        ),
    },
]


CONTENT_REGISTRY = {
    "v1": {
        "release_status": "RELEASED",
        "offers": BASE_OFFER_DEFINITIONS,
    },
}


def _money(cents):
    return f"${cents / 100:.2f}"


def calculate_prices(offer, variant_key):
    base = offer["variants"][variant_key]["base"]
    offer_type = offer["offer_type"]
    if offer_type == "SECOND_ITEM_PERCENT":
        second = round(base * offer["parameters"]["second_item_rate"])
        return base, second, base + second
    if offer_type == "PERCENT_OFF":
        discount = round(base * offer["parameters"]["discount_rate"])
        return base, discount, base - discount
    if offer_type == "BUY_X_GET_Y":
        return base, 0, base
    amount_off = offer["parameters"]["amount_off_cents"]
    return base, amount_off, base - amount_off


def build_questions(offer, variant_key, content_version=CONTENT_VERSION):
    base, secondary, total = calculate_prices(offer, variant_key)
    offer_type = offer["offer_type"]

    if offer_type == "SECOND_ITEM_PERCENT":
        meaning = {
            "prompt_en": "How much does the second bun cost?",
            "answer": secondary,
            "rule_hint": "Only the second bun is discounted; it costs 50% of the original price.",
            "formula_hint": f"{_money(base)} × 50% = ?",
            "correct_feedback": f"Correct. The second bun costs {_money(secondary)}.",
            "misconceptions": {},
        }
        price = {
            "prompt_en": "What is the total price for both pepper buns?",
            "answer": total,
            "rule_hint": "Add the full-price first bun and the half-price second bun.",
            "formula_hint": f"{_money(base)} + {_money(secondary)} = ?",
            "correct_feedback": f"Correct. Both pepper buns cost {_money(total)} in total.",
            "misconceptions": (
                {
                    str(secondary): (
                        "SECOND_ITEM_ONLY",
                        "That is only the discounted second bun's price, not the total. "
                        "Add the full-price first bun as well.",
                    ),
                    str(base): (
                        "BOTH_ITEMS_TREATED_AS_ONE_FULL_PRICE",
                        "That total accounts for only one full-price bun or discounts "
                        "both buns. The first bun is full price and the second is half "
                        "price; add both prices.",
                    ),
                }
                if content_version == "v1"
                else {
                    str(secondary): (
                        "SECOND_ITEM_ONLY",
                        "That is only the second bun's price. Add the full-price first bun too.",
                    ),
                    str(base): (
                        "DISCOUNTED_BOTH_ITEMS",
                        "The first bun stays at full price; only the second bun is discounted.",
                    ),
                }
            ),
        }
    elif offer_type == "PERCENT_OFF":
        rate = round(offer["parameters"]["discount_rate"] * 100)
        meaning = {
            "prompt_en": f"How much is taken off the {_money(base)} original price?",
            "answer": secondary,
            "rule_hint": f"Find {rate}% of the original price.",
            "formula_hint": f"{_money(base)} × {rate}% = ?",
            "correct_feedback": f"Correct. The discount amount is {_money(secondary)}.",
            "misconceptions": (
                {
                    str(total): (
                        "FINAL_PRICE_AS_DISCOUNT_AMOUNT",
                        "That is the price after the discount. The question asks how "
                        "much is taken off.",
                    )
                }
                if content_version == "v1"
                else {}
            ),
        }
        price = {
            "prompt_en": "What price do you pay after the discount?",
            "answer": total,
            "rule_hint": "Subtract the discount amount from the original price.",
            "formula_hint": f"{_money(base)} − {_money(secondary)} = ?",
            "correct_feedback": f"Correct. You pay {_money(total)}.",
            "misconceptions": (
                {
                    str(secondary): (
                        "DISCOUNT_AMOUNT_AS_FINAL_PRICE",
                        "That is the amount taken off, not the final price. Subtract "
                        "it from the original price.",
                    ),
                    str(base): (
                        "NO_DISCOUNT_APPLIED",
                        "That is the original price. Apply the discount before paying.",
                    ),
                }
                if content_version == "v1"
                else {
                    str(secondary): (
                        "DISCOUNT_AMOUNT_AS_FINAL_PRICE",
                        "That is the discount amount, not the final price.",
                    ),
                    str(max(0, base - rate * 100)): (
                        "PERCENT_SUBTRACTED_AS_DOLLARS",
                        "A percentage must be calculated from the original price before subtracting it.",
                    ),
                }
            ),
        }
    elif offer_type == "BUY_X_GET_Y":
        meaning = {
            "prompt_en": "How much does the second rice pudding cost?",
            "answer": 0,
            "rule_hint": "You pay full price for the first item; the second item is free.",
            "formula_hint": "Second item price = $0.00",
            "correct_feedback": "Correct. The second rice pudding is free.",
            "misconceptions": {},
        }
        price = {
            "prompt_en": "What is the total price for both rice puddings?",
            "answer": total,
            "rule_hint": "The first item is full price and the second item is free.",
            "formula_hint": f"{_money(base)} + $0.00 = ?",
            "correct_feedback": f"Correct. Both rice puddings cost {_money(total)} in total.",
            "misconceptions": (
                {
                    "0": (
                        "FREE_ITEM_MEANS_TOTAL_IS_ZERO",
                        "Only the second item is free. The first item is still full price.",
                    ),
                    str(base * 2): (
                        "NO_FREE_ITEM_APPLIED",
                        "The second item is free, so do not charge both items at full price.",
                    ),
                }
                if content_version == "v1"
                else {
                    "0": (
                        "FREE_ITEM_MEANS_TOTAL_IS_ZERO",
                        "Only the second item is free; the first item is still full price.",
                    )
                }
            ),
        }
    else:
        meaning = {
            "prompt_en": f"How much is taken off the {_money(base)} original price?",
            "answer": secondary,
            "rule_hint": "Use the fixed amount stated by the offer.",
            "formula_hint": f"Discount amount = {_money(secondary)}",
            "correct_feedback": f"Correct. The discount amount is {_money(secondary)}.",
            "misconceptions": {},
        }
        price = {
            "prompt_en": "What price do you pay after the discount?",
            "answer": total,
            "rule_hint": "Subtract the fixed discount from the original price.",
            "formula_hint": f"{_money(base)} − {_money(secondary)} = ?",
            "correct_feedback": f"Correct. You pay {_money(total)}.",
            "misconceptions": (
                {
                    str(secondary): (
                        "DISCOUNT_AMOUNT_AS_FINAL_PRICE",
                        "That is the discount amount, not the final price. Subtract it "
                        "from the original price.",
                    ),
                    str(base): (
                        "NO_DISCOUNT_APPLIED",
                        "That is the original price. Subtract the fixed discount before paying.",
                    ),
                }
                if content_version == "v1"
                else {
                    str(secondary): (
                        "DISCOUNT_AMOUNT_AS_FINAL_PRICE",
                        "That is the discount amount, not the final price.",
                    )
                }
            ),
        }

    transfer_key = offer["transfer_variant"][variant_key]
    transfer_base, _, transfer_total = calculate_prices(offer, transfer_key)
    if offer_type == "SECOND_ITEM_PERCENT":
        transfer_prompt = (
            f"Challenge: If each bun cost {_money(transfer_base)} with the same offer, "
            "what would two buns cost?"
        )
    elif offer_type == "BUY_X_GET_Y":
        transfer_prompt = (
            f"Challenge: If each pudding cost {_money(transfer_base)} with the same offer, "
            "what would two cost?"
        )
    else:
        transfer_prompt = (
            f"Challenge: A different item costs {_money(transfer_base)} with the same offer. "
            "What price would you pay?"
        )
    transfer = {
        "prompt_en": transfer_prompt,
        "answer": transfer_total,
        "rule_hint": "Apply the same offer rule to the new original price.",
        "formula_hint": "Apply the previously learned rule to the new price.",
        "correct_feedback": f"Correct. The new price is {_money(transfer_total)}.",
        "misconceptions": {},
        "source_variant": transfer_key,
    }

    return [
        {"skill": "RULE_MEANING", "order": 1, **meaning},
        {"skill": "PRICE_CALCULATION", "order": 2, **price},
        {"skill": "TRANSFER", "order": 3, **transfer},
    ]


def get_offer_definitions(content_version=CONTENT_VERSION):
    version = CONTENT_REGISTRY.get(content_version)
    return deepcopy(version["offers"]) if version else None


def get_offer_definition(content_version, offer_id=None):
    # Backward-compatible form: get_offer_definition(offer_id)
    if offer_id is None:
        offer_id = content_version
        content_version = CONTENT_VERSION
    offers = get_offer_definitions(content_version) or []
    for offer in offers:
        if offer["offer_id"] == offer_id:
            return deepcopy(offer)
    return None


def get_offer_by_node(node_id, content_version=CONTENT_VERSION):
    for offer in get_offer_definitions(content_version) or []:
        if node_id in (offer["root_node_id"], offer["offer_node_id"]):
            return deepcopy(offer)
    return None


def approved_variant_keys(offer):
    return [key for key, variant in offer["variants"].items() if variant["approved"]]


def selectable_variant_keys(content_version, offer, allow_unreleased=False):
    if content_version in SUPPORTED_CONTENT_VERSIONS:
        return approved_variant_keys(offer)
    if content_version in UNRELEASED_CONTENT_VERSIONS and allow_unreleased:
        return list(offer["variants"].keys())
    return []


def select_variant_key(content_version, offer, seed, allow_unreleased=False):
    selectable = selectable_variant_keys(
        content_version, offer, allow_unreleased=allow_unreleased
    )
    if not selectable:
        return None
    digest = hashlib.sha256(
        f"{content_version}:{seed}:{offer['offer_id']}".encode("utf-8")
    ).digest()
    return selectable[int.from_bytes(digest[:8], "big") % len(selectable)]


def ordered_offer_definitions(content_version, seed):
    offers = get_offer_definitions(content_version) or []
    return sorted(
        offers,
        key=lambda offer: hashlib.sha256(
            f"{content_version}:{seed}:order:{offer['offer_id']}".encode("utf-8")
        ).digest(),
    )


def content_catalog(content_version=CONTENT_VERSION):
    """Return all 45 versioned question templates for review tooling."""
    catalog = []
    for offer in get_offer_definitions(content_version) or []:
        for variant_key, variant in offer["variants"].items():
            if content_version == "v1":
                audio_greet = (
                    f"/audio-clips/{offer['root_node_id']}.wav"
                    if variant_key == "A"
                    else f"/audio-clips/{offer['root_node_id']}_{variant_key}.wav"
                )
                audio_offer = f"/audio-clips/{offer['offer_node_id']}.wav"
            else:
                audio_greet = (
                    f"/audio-clips/{offer['root_node_id']}.wav"
                    if variant_key == "A"
                    else ""
                )
                audio_offer = (
                    f"/audio-clips/{offer['offer_node_id']}.wav"
                    if variant_key == "A"
                    else ""
                )
            catalog.append(
                {
                    "content_version": content_version,
                    "offer_id": offer["offer_id"],
                    "variant": variant_key,
                    "content_status": variant["status"],
                    "approved": variant["approved"],
                    "selectable_for_session": variant["approved"],
                    "dialogue": {
                        "greet": offer["greet"][variant_key],
                        "offer": offer["offer_dialogue"],
                        "audio_greet": audio_greet,
                        "audio_offer": audio_offer,
                    },
                    "questions": build_questions(
                        offer, variant_key, content_version=content_version
                    ),
                }
            )
    return catalog
