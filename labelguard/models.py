from datetime import date
from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictBool, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=250)]
Mass = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Category(str, Enum):
    cereal = "breakfast_cereal"
    dairy = "dairy"
    supplement = "supplement"
    beverage = "beverage"
    other = "other"


class Ingredient(Contract):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    percent: Annotated[float, Field(gt=0, le=100, allow_inf_nan=False, strict=True)] | None = None


class Nutrition(Contract):
    basis: Literal["per_100g", "per_serving"] = "per_100g"
    energy_kcal: Annotated[float, Field(ge=0, le=950, allow_inf_nan=False, strict=True)] | None = None
    protein_g: Mass | None = None
    carbohydrate_g: Mass | None = None
    total_sugars_g: Mass | None = None
    added_sugars_g: Mass | None = None
    total_fat_g: Mass | None = None
    saturated_fat_g: Mass | None = None
    trans_fat_g: Mass | None = None
    fibre_g: Mass | None = None
    sodium_mg: Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False, strict=True)] | None = None
    cholesterol_mg: Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False, strict=True)] | None = None
    serving_size_g: Annotated[float, Field(gt=0, le=1000, allow_inf_nan=False, strict=True)] | None = None
    servings_per_pack: Annotated[float, Field(gt=0, le=1000, allow_inf_nan=False, strict=True)] | None = None
    rda_percent_declared: StrictBool = False

    @model_validator(mode="after")
    def consistent(self):
        for lower, upper in [
            ("added_sugars_g", "total_sugars_g"),
            ("total_sugars_g", "carbohydrate_g"),
            ("saturated_fat_g", "total_fat_g"),
            ("trans_fat_g", "total_fat_g"),
        ]:
            a, b = getattr(self, lower), getattr(self, upper)
            if a is not None and b is not None and a > b:
                raise ValueError(f"{lower} must not exceed {upper}")
        if self.basis == "per_serving" and self.serving_size_g is None:
            raise ValueError("serving_size_g is required for per_serving nutrition")
        factor = 100 / self.serving_size_g if self.basis == "per_serving" else 1
        for key in ["protein_g", "carbohydrate_g", "total_fat_g", "total_sugars_g", "fibre_g"]:
            value = getattr(self, key)
            if value is not None and value * factor > 100.001:
                raise ValueError(f"{key} exceeds 100 g after normalisation")
        mass = sum(getattr(self, k) or 0 for k in ["protein_g", "carbohydrate_g", "total_fat_g"])
        if mass * factor > 100.001:
            raise ValueError("protein + carbohydrate + fat must not exceed 100 g per 100 g")
        if self.energy_kcal is not None and self.energy_kcal * factor > 950:
            raise ValueError("energy exceeds 950 kcal per 100 g after normalisation")
        return self

    def per100(self, field: str) -> float | None:
        value = getattr(self, field)
        if value is None:
            return None
        return value * (100 / self.serving_size_g if self.basis == "per_serving" else 1)


class Package(Contract):
    net_quantity_g: Annotated[float, Field(gt=0, le=50000, allow_inf_nan=False, strict=True)]
    surface_area_cm2: Annotated[float, Field(gt=0, le=100000, allow_inf_nan=False, strict=True)]
    retail: StrictBool = True
    imported: StrictBool = False
    single_ingredient_unprocessed: StrictBool = False
    exemption_claimed: StrictBool = False


class Declarations(Contract):
    food_name: ShortText = ""
    ingredients: Annotated[list[Ingredient], Field(max_length=60)] = []
    allergens: Annotated[list[ShortText], Field(max_length=30)] = []
    veg_mark: Literal["veg", "non_veg", "missing"] = "missing"
    animal_fat_present: StrictBool = False
    fssai_logo: StrictBool = False
    licence_number: Annotated[str, StringConstraints(pattern=r"^(\d{14})?$")] = ""
    brand_owner_name: ShortText = ""
    brand_owner_address: Text = ""
    manufacturer_same_as_owner: StrictBool = True
    manufacturer_name: ShortText = ""
    manufacturer_address: Text = ""
    manufacturer_licence: Annotated[str, StringConstraints(pattern=r"^(\d{14})?$")] = ""
    batch_number: ShortText = ""
    manufacture_date: date | None = None
    expiry_date: date | None = None
    net_quantity_declared: StrictBool = False
    mrp_declared: StrictBool = False
    consumer_care_declared: StrictBool = False
    instructions_for_use: Text = ""
    language: Literal["en", "hi", "other"] = "en"


class RDABasis(Contract):
    protein_g_per_day: Annotated[float, Field(gt=0, le=200, allow_inf_nan=False, strict=True)]
    reference: Annotated[str, StringConstraints(min_length=10, max_length=500)]
    target_population: Annotated[str, StringConstraints(min_length=3, max_length=200)]
    confirmed_by_reviewer: StrictBool = False


class LabelRequest(Contract):
    contract_version: Literal["1.0"] = "1.0"
    product_name: Annotated[str, StringConstraints(min_length=2, max_length=200)]
    category: Category
    front_of_pack: Text = ""
    other_label_text: Text = ""
    claims: Annotated[list[ShortText], Field(max_length=20)] = []
    package: Package
    declarations: Declarations
    nutrition: Nutrition
    rda_basis: RDABasis | None = None
    assessment_date: date = date(2026, 10, 27)

    @model_validator(mode="after")
    def cross_fields(self):
        d, n = self.declarations, self.nutrition
        if d.manufacture_date and d.expiry_date and d.expiry_date <= d.manufacture_date:
            raise ValueError("expiry_date must be later than manufacture_date")
        ingredients = d.ingredients
        if sum(i.percent or 0 for i in ingredients) > 100.01:
            raise ValueError("ingredient percentages must not exceed 100")
        known = [i.percent for i in ingredients if i.percent is not None]
        if len(known) == len(ingredients) and known != sorted(known, reverse=True):
            raise ValueError("ingredient percentages must be in descending weight order")
        if n.serving_size_g and n.serving_size_g > self.package.net_quantity_g:
            raise ValueError("serving_size_g must not exceed net_quantity_g")
        if n.serving_size_g and n.servings_per_pack:
            expected = self.package.net_quantity_g / n.serving_size_g
            if abs(expected - n.servings_per_pack) > max(0.1, expected * 0.05):
                raise ValueError(
                    "servings_per_pack conflicts with net quantity and serving size (5% tolerance)"
                )
        return self


class Citation(Contract):
    passage_id: str
    document: str
    clause: str
    page: int
    source_url: str
    quote: str
    sha256: str


class Finding(Contract):
    requirement: str
    status: Literal["met", "unmet", "insufficient_evidence", "not_applicable"]
    explanation: str
    citations: list[Citation] = []
    observed: dict = {}


class Recommendation(Contract):
    route: Literal["clear-for-print", "revise-and-recheck", "regulatory-review"]
    summary: str
    findings: list[Finding]
    print_authorized: Literal[False] = False
    human_action: str = "A regulatory affairs professional must review the evidence and decide on printing."
    prompt_version: str
    corpus_version: str
    mode: str
    verified: bool
    limitations: list[str] = []


class Feedback(Contract):
    satisfactory: StrictBool
    reason: Annotated[str, StringConstraints(min_length=3, max_length=1000)]
