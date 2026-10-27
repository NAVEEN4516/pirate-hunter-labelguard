"""Small, auditable rule registry. LLMs retrieve; checked arithmetic decides findings."""

import re
from datetime import date
from .models import LabelRequest, Recommendation, Finding

CLAIMS = {
    "source_protein": r"\b(?:(?:source|contains|provides|with)(?:\s+of)?\s+protein|protein\s+source)\b",
    "high_protein": r"\b(?:(?:high|rich)(?:\s+(?:in|of))?\s+protein|protein[ -]rich)\b",
    "low_sugar": r"\blow[ -](?:in[ -])?sugars?\b",
    "sugar_free": r"\b(?:sugars?[ -]free|free[ -](?:of|from)[ -]sugars?)\b",
    "source_fibre": r"\b(?:source(?:\s+of)?|contains|provides|with)\s+fib(?:re|er)\b",
    "high_fibre": r"\b(?:high|rich)(?:\s+(?:in|of))?\s+fib(?:re|er)\b",
}
UNSUPPORTED = re.compile(
    r"\b(?:cure|treat|prevent|diabet|cancer|immunity|immune|organic|natural|fresh|pure|gluten|lactose|no added|sodium|low fat|zero fat|vegan|fortified|100\s*%|protein[ -]packed|healthy|reduced|more protein)\w*",
    re.I,
)
CLAUSE_FOR_CLAIM = {
    "source_protein": "AC-PROTEIN",
    "high_protein": "AC-PROTEIN",
    "low_sugar": "AC-SUGARS",
    "sugar_free": "AC-SUGARS",
    "source_fibre": "AC-FIBRE",
    "high_fibre": "AC-FIBRE",
}
MANDATORY = [
    "LD-4",
    "LD-5.1",
    "LD-5.2",
    "LD-5.3",
    "LD-5.4",
    "LD-5.6",
    "LD-5.7",
    "LD-5.8",
    "LD-5.9",
    "LD-5.10",
    "LD-5.14",
]
LIMITATIONS = [
    "Findings cover the implemented checks for domestic retail processed breakfast cereals only.",
    "Structured declarations are the proposed label data; artwork, font, symbol dimensions and placement are not inspected.",
    "Licence authenticity, ingredient exemptions, manufacturing evidence and detailed Legal Metrology requirements need a professional check.",
    "Claim arithmetic is conditional on the supplied RDA basis and declared values; laboratory substantiation is not validated.",
]


def detect_claims(request: LabelRequest):
    text = " ".join([request.front_of_pack, request.other_label_text, *request.claims])
    detected = [key for key, pattern in CLAIMS.items() if re.search(pattern, text, re.I)]
    unknown = [
        claim
        for claim in request.claims
        if claim and not any(re.search(pattern, claim, re.I) for pattern in CLAIMS.values())
    ]
    unknown.extend(m.group(0) for m in UNSUPPORTED.finditer(text))
    return {"detected": sorted(set(detected)), "unsupported": sorted(set(unknown))}


def scope_issues(request):
    issues = []
    if request.category.value != "breakfast_cereal":
        issues.append("The declared category is outside the breakfast-cereal corpus.")
    if not re.search(
        r"cereal|granola|muesli|corn\s?flakes|bran\s?flakes|porridge|oats",
        request.product_name + " " + request.declarations.food_name,
        re.I,
    ):
        issues.append(
            "The product name does not establish a breakfast-cereal category; confirm classification."
        )
    if re.search(
        r"infant|baby|supplement|medical|toddler", request.product_name + " " + request.front_of_pack, re.I
    ):
        issues.append("A special-population or supplement category may apply.")
    p = request.package
    if p.surface_area_cm2 <= 100 or p.exemption_claimed or p.single_ingredient_unprocessed:
        issues.append(
            "A small-package or product exemption may apply; professional interpretation is required."
        )
    if not p.retail or p.imported:
        issues.append("Non-retail or imported packages are outside the implemented domestic retail scope.")
    if request.assessment_date < date(2025, 9, 9) or request.assessment_date >= date(2027, 7, 1):
        issues.append("The assessment date is outside the confirmed corpus applicability window.")
    d = request.declarations
    if d.manufacture_date and d.expiry_date and (d.expiry_date - d.manufacture_date).days <= 7:
        issues.append("A shelf life of seven days or less may qualify for a date-marking exemption.")
    if not d.manufacturer_same_as_owner:
        issues.append(
            "Separate manufacturer/brand owner declarations require additional professional checking."
        )
    if detect_claims(request)["unsupported"]:
        issues.append(
            "At least one claim is outside the implemented claim rules; review all applicable provisions."
        )
    return issues


def required_ids(request):
    claims = detect_claims(request)["detected"]
    ids = set(MANDATORY)
    if claims:
        ids.update(["AC-5.3", "AC-4.6"])
        ids.update(CLAUSE_FOR_CLAIM[c] for c in claims)
    if any("protein" in c for c in claims):
        ids.add("AC-RDA")
    if request.package.surface_area_cm2 <= 100 or request.package.exemption_claimed:
        ids.add("LD-8")
    if detect_claims(request)["unsupported"]:
        ids.add("AC-10")
    return sorted(ids)


def evaluate(request: LabelRequest, passages: list[dict], corpus, prompt_version="v2", degraded_reason=None):
    available = {p["id"]: p for p in passages}
    findings = []

    def add(requirement, condition, explanation, clause_ids, observed=None, insufficient=False):
        missing = [i for i in clause_ids if i not in available]
        status = "insufficient_evidence" if missing or insufficient else ("met" if condition else "unmet")
        if missing:
            explanation = (
                "Evidence is incomplete: retrieve " + ", ".join(missing) + ". No determination returned."
            )
        findings.append(
            Finding(
                requirement=requirement,
                status=status,
                explanation=explanation,
                citations=[corpus.citation(available[i]) for i in clause_ids if i in available],
                observed=observed or {},
            )
        )

    d, n = request.declarations, request.nutrition
    add(
        "food_name",
        bool(d.food_name),
        "A food name is declared."
        if d.food_name
        else "Declare a name indicating the true nature of the food.",
        ["LD-5.1"],
    )
    add(
        "ingredients",
        bool(d.ingredients),
        "An ingredient list is declared; composition and completeness require manufacturer confirmation."
        if d.ingredients
        else "Declare the ingredients in descending order of composition.",
        ["LD-5.2"],
    )
    fields = [
        "energy_kcal",
        "protein_g",
        "carbohydrate_g",
        "total_sugars_g",
        "added_sugars_g",
        "total_fat_g",
        "sodium_mg",
        "serving_size_g",
        "servings_per_pack",
    ]
    if (n.per100("total_fat_g") or 0) > 0.5:
        fields.extend(["saturated_fat_g", "trans_fat_g"])
        if d.animal_fat_present:
            fields.append("cholesterol_mg")
    absent = [f for f in fields if getattr(n, f) is None]
    if not n.rda_percent_declared:
        absent.append("per-serve percentage contribution to RDA")
    add(
        "nutrition_panel",
        not absent,
        "Required numeric declarations are present in the supported panel."
        if not absent
        else "Missing nutrition declarations: " + ", ".join(absent) + ".",
        ["LD-5.3"],
        {"missing_fields": absent, "basis": n.basis},
    )
    # This demo requires per-100g declarations for multi-serve cereal: per-serving alone
    # is not one of the general alternatives in LD 5(3)(b) for a multi-serve pack.
    if n.basis == "per_serving" and (n.servings_per_pack or 2) > 1:
        add(
            "nutrition_basis",
            False,
            "Add per-100g nutrition for this multi-serving solid package; per-serving-only values do not establish the required general basis.",
            ["LD-5.3"],
        )
    egg_or_meat = bool(
        re.search(
            r"\b(?:egg|chicken|fish|gelatin|gelatine|beef|pork)\b",
            " ".join(i.name for i in d.ingredients),
            re.I,
        )
    )
    correct_mark = d.veg_mark == ("non_veg" if egg_or_meat else "veg")
    add(
        "veg_mark",
        correct_mark,
        "The declared mark agrees with the supported ingredient screen; artwork requires inspection."
        if correct_mark
        else "Provide the correct vegetarian/non-vegetarian mark and confirm ingredients and processing aids.",
        ["LD-5.4"],
    )
    add(
        "brand_owner",
        bool(d.brand_owner_name and d.brand_owner_address),
        "Brand-owner name and address are declared."
        if d.brand_owner_name and d.brand_owner_address
        else "Declare brand-owner name and complete address.",
        ["LD-5.6"],
    )
    add(
        "fssai_declaration",
        bool(d.fssai_logo and d.licence_number),
        "FSSAI logo and a 14-digit licence declaration are present; authenticity is not checked."
        if d.fssai_logo and d.licence_number
        else "Declare the FSSAI logo and licence number.",
        ["LD-5.7"],
    )
    quantity = d.net_quantity_declared and d.mrp_declared and d.consumer_care_declared
    add(
        "quantity_price_care_presence",
        quantity,
        "Net quantity, price and consumer care are declared. Detailed Legal Metrology compliance remains outside the corpus."
        if quantity
        else "Provide net quantity, retail price and consumer care particulars; the cited clause refers to Legal Metrology for details.",
        ["LD-5.8"],
    )
    add(
        "batch",
        bool(d.batch_number),
        "Batch identification is declared." if d.batch_number else "Declare a lot, code or batch identifier.",
        ["LD-5.9"],
    )
    add(
        "dates",
        bool(d.manufacture_date and d.expiry_date),
        "Manufacture and expiry/use-by dates are declared."
        if d.manufacture_date and d.expiry_date
        else "Declare manufacture/packaging and expiry/use-by dates; best-before alone is insufficient.",
        ["LD-5.10"],
    )
    allergen_patterns = {
        "wheat": r"wheat",
        "oats": r"oats?",
        "barley": r"barley",
        "rye": r"\brye\b",
        "milk": r"milk|whey|casein|butter",
        "soy": r"soy",
        "egg": r"\begg",
        "nut": r"almond|cashew|walnut|pistachio|peanut|hazelnut|pecan",
    }
    ingredient_text = " ".join(i.name for i in d.ingredients)
    declared = " ".join(d.allergens).lower()
    needed = [
        name for name, pattern in allergen_patterns.items() if re.search(pattern, ingredient_text, re.I)
    ]
    missing = [
        name
        for name in needed
        if name not in declared
        and not (name == "nut" and re.search(r"almond|cashew|walnut|peanut|pistachio", declared))
    ]
    add(
        "allergens",
        not missing,
        "Known allergens from the supported ingredient screen are separately declared."
        if not missing
        else "Add separate Contains declarations for: " + ", ".join(missing) + ".",
        ["LD-5.14"],
        {"detected": needed, "missing": missing},
    )
    add(
        "language",
        d.language in ("en", "hi"),
        "English or Hindi is declared as a label language."
        if d.language in ("en", "hi")
        else "Provide mandatory declarations in English or Hindi.",
        ["LD-4"],
    )
    claims = detect_claims(request)
    for claim in claims["detected"]:
        ids = ["LD-5.3", "AC-5.3", CLAUSE_FOR_CLAIM[claim]]
        if "protein" in claim:
            ids.append("AC-RDA")
            protein, energy, serving = n.per100("protein_g"), n.per100("energy_kcal"), n.serving_size_g
            if not request.rda_basis or not request.rda_basis.confirmed_by_reviewer or protein is None:
                add(
                    claim,
                    False,
                    "Supply protein and an applicable, reviewer-confirmed ICMR RDA benchmark before determining this claim.",
                    ids,
                    insufficient=True,
                )
                continue
            rda = request.rda_basis.protein_g_per_day
            fraction = 0.2 if claim == "high_protein" else 0.1
            threshold_100g, threshold_100kcal = rda * fraction, rda * fraction / 2
            per100kcal = protein * 100 / energy if energy and energy > 0 else None
            perserve = protein * serving / 100 if serving else None
            branches = {
                "per_100g": protein >= threshold_100g - 1e-9,
                "per_100kcal": per100kcal is not None and per100kcal >= threshold_100kcal - 1e-9,
                "per_serving": perserve is not None and perserve >= threshold_100g - 1e-9,
            }
            meets = any(branches.values())
            incomplete = not meets and (per100kcal is None or perserve is None)
            observation = {
                "protein_per_100g": protein,
                "protein_per_100kcal": per100kcal,
                "protein_per_serving": perserve,
                "rda_g": rda,
                "threshold_per_100g": threshold_100g,
                "threshold_per_100kcal": threshold_100kcal,
                "threshold_per_serving": threshold_100g,
                "qualifying_branches": [k for k, v in branches.items() if v],
                "rda_reference": request.rda_basis.reference,
            }
            explanation = (
                f"Declared protein is {protein:g} g/100g. With the supplied {rda:g} g/day RDA, compare >= {threshold_100g:g} g/100g OR >= {threshold_100kcal:g} g/100kcal OR >= {threshold_100g:g} g/serving. "
                + (
                    "At least one solid-food condition is met, conditional on the benchmark and substantiation."
                    if meets
                    else "No evaluated condition is met; revise the claim or declared formulation."
                )
            )
            if incomplete:
                explanation = "A protein condition does not pass on known data and another alternative cannot be evaluated; supply energy and serving size."
            add(claim, meets, explanation, ids, observation, insufficient=incomplete)
        elif "sugar" in claim:
            sugar = n.per100("total_sugars_g")
            threshold = 0.5 if claim == "sugar_free" else 5
            add(
                claim,
                sugar is not None and sugar <= threshold,
                f"Compare total sugars ({sugar} g/100g) with <= {threshold:g} g/100g for this claim.",
                ids,
                {"sugars_per_100g": sugar, "threshold": threshold},
                insufficient=sugar is None,
            )
        else:
            fibre, energy = n.per100("fibre_g"), n.per100("energy_kcal")
            threshold = 6 if claim == "high_fibre" else 3
            per100kcal = fibre * 100 / energy if fibre is not None and energy and energy > 0 else None
            meets = fibre is not None and (
                fibre >= threshold or (per100kcal is not None and per100kcal >= threshold / 2)
            )
            add(
                claim,
                meets,
                f"Compare fibre ({fibre} g/100g) with >= {threshold} g/100g OR >= {threshold / 2:g} g/100kcal.",
                ids,
                {"fibre_per_100g": fibre, "fibre_per_100kcal": per100kcal},
                insufficient=fibre is None or (not meets and per100kcal is None),
            )
    issues = scope_issues(request)
    if issues:
        add(
            "scope_and_exemptions",
            False,
            " ".join(issues),
            ["LD-8"] if "LD-8" in required_ids(request) else ["LD-4"],
            {"issues": issues, "unsupported_claims": claims["unsupported"]},
            insufficient=True,
        )
    missing_ids = set(required_ids(request)) - available.keys()
    if missing_ids:
        add(
            "evidence_coverage",
            False,
            "Required evidence has not been retrieved: " + ", ".join(sorted(missing_ids)),
            sorted(missing_ids),
            insufficient=True,
        )
    if degraded_reason:
        add(
            "service_reliability",
            False,
            "Research could not complete: " + degraded_reason,
            [],
            insufficient=True,
        )
    review = any(f.status == "insufficient_evidence" for f in findings)
    revise = any(f.status == "unmet" for f in findings)
    route = "regulatory-review" if review else "revise-and-recheck" if revise else "clear-for-print"
    summary = {
        "regulatory-review": "Human review required: evidence, scope or service reliability is incomplete.",
        "revise-and-recheck": "Revise the unmet declarations or claims and submit the label again.",
        "clear-for-print": "No issues detected in the supported checks. A professional must decide whether to print.",
    }[route]
    return Recommendation(
        route=route,
        summary=summary,
        findings=findings,
        prompt_version=prompt_version,
        corpus_version=corpus.manifest["version"],
        mode=settings_mode(),
        verified=True,
        limitations=LIMITATIONS,
    ).model_dump(mode="json")


def settings_mode():
    from .config import settings

    return settings().provider_mode


def verify(candidate, request, passages, corpus, prompt_version, degraded_reason=None):
    """Exact deterministic policy recomputation + citation resolution, independent of model output."""
    expected = evaluate(request, passages, corpus, prompt_version, degraded_reason)
    problems = []
    allowed = {p["id"]: p for p in passages}
    if candidate != expected:
        problems.append("Candidate differs from independently recomputed policy findings or arithmetic.")
    for finding in candidate.get("findings", []):
        for citation in finding.get("citations", []):
            passage = allowed.get(citation.get("passage_id"))
            if not passage or corpus.citation(passage) != citation:
                problems.append("Citation does not resolve exactly to a retrieved passage.")
    from .guardrails import safe_output

    if not safe_output(candidate):
        problems.append("Output guardrail rejected the candidate.")
    return not problems, sorted(set(problems)), expected
