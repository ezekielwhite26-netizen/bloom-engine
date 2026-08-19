from bloom_engine.hecate.airtable_store import (
    AirtableHecateStore,
    AirtableSnapshot,
    FOCUS_BONDS_TABLE,
    MAGICAL_CONDITIONS_TABLE,
    MAGIC_FORMS_TABLE,
    MAGIC_PROFILES_TABLE,
)


FLORENCE = "BLM-CHR-000001"
PASSAGE = "HEC-FORM-SIG-PASSAGE"


def linked(name: str):
    return [{"id": "recXXXXXXXXXXXXXX", "name": name}]


def make_snapshot() -> AirtableSnapshot:
    return AirtableSnapshot(
        tables={
            MAGIC_FORMS_TABLE: [
                {
                    "cellValuesByFieldId": {
                        "fld45Hpr1qg2aiMQH": PASSAGE,
                        "fldCnGxg9KWAEFTDi": "Passage",
                        "fldViW7pE3nknrYAq": "Works the transition between genuinely connected states.",
                        "fldPbLfdMcTKDgyfh": "A genuine connection and endpoint must already exist.",
                        "fld2vnwfRP3C9YxT8": "Uses established Working structure.",
                        "fld1GeZD0TgR42A7M": "Mirror relation; ring continuity; needle crossing; thread continuity; shears release.",
                        "fldJ4xluUJ4JW84M0": "Cannot invent an endpoint.",
                        "fld2JJmmETj54axO7": "Heat is practitioner strain, not mana; no numeric scale is established.",
                        "fldF6xBBEOfxtIZ5j": "Release/Clearing remains required.",
                        "fldYP4gZGlk20K0eq": {"name": "READY"},
                        "fldBguuZ5O47gffcx": "Definitive Runtime Master; Episode 6 audit.",
                        "fldVGA7HswNBd7NLa": "Directly practiced in Episode 6.",
                        "fldvJviqRreNOzcz2": "Do not infer numeric Heat or an invented endpoint.",
                    }
                }
            ],
            MAGIC_PROFILES_TABLE: [
                {
                    "cellValuesByFieldId": {
                        "flduA8NQAjjygYMB2": "HEC-PROF-FLORENCE-MACKELLAR",
                        "fldBt9Kw2SN4fCZMZ": "Florence Maeve MacKellar",
                        "fldtcIVcPThrH17ep": linked(FLORENCE),
                        "fldvogs2xoN6k0Bx1": linked(PASSAGE),
                        "fldmQhtUwK9fUXozw": linked("HEC-FORM-FAC-GENERAL-REVELATION"),
                        "fldBLRIjuGmX7X2o1": "Passage plus General Revelation.",
                        "fld41oiui1YtpCN50": "No active magical condition asserted by this profile.",
                        "fldyU3HzHxQme6lIR": "Do not infer physical Focus availability.",
                        "fldYU0mlIswikBkzh": {"name": "PARTIAL"},
                        "fldYPXEtRjEWIbRjR": "Definitive Runtime Master; Episode 6 audit.",
                    }
                }
            ],
            FOCUS_BONDS_TABLE: [
                {
                    "cellValuesByFieldId": {
                        "fldNcJT4T0guLFMbj": "HEC-FOCUS-FLORENCE-MIRROR",
                        "fldnOylIgrju44d8V": linked(FLORENCE),
                        "fldouMkB9g6p72Vsr": "Florence’s antique folding mirror",
                        "fldO1A7ps6H6xDpCp": linked("BLM-OBJ-000001"),
                        "fldaQKgq4w2UEbmhS": linked(PASSAGE),
                        "fldJtbxCwV6qcDMxX": {"name": "Active Focus"},
                        "fld0UXExoNkgqxif6": "Externalizes relation/witness.",
                        "fldSjSLodQ3YSSnni": "Focus status does not prove scene presence.",
                        "fldGvSTR1jMuyieUi": {"name": "READY"},
                        "fldyaKn9rPFx5y9gh": "Runtime Master; Episode 6 audit.",
                    }
                },
                {
                    "cellValuesByFieldId": {
                        "fldNcJT4T0guLFMbj": "HEC-NONFOCUS-FLORENCE-LEAF-HAIRPIN",
                        "fldnOylIgrju44d8V": linked(FLORENCE),
                        "fldouMkB9g6p72Vsr": "Enchanted brass leaf hairpin",
                        "fldO1A7ps6H6xDpCp": linked("BLM-OBJ-000005"),
                        "fldJtbxCwV6qcDMxX": {"name": "Explicitly Not Focus"},
                        "fld0UXExoNkgqxif6": "None established as a Focus.",
                        "fldSjSLodQ3YSSnni": "Do not promote from enchantment or aesthetics.",
                        "fldGvSTR1jMuyieUi": {"name": "READY"},
                        "fldyaKn9rPFx5y9gh": "Episode 6 audit; object record.",
                    }
                },
            ],
            MAGICAL_CONDITIONS_TABLE: [
                {
                    "cellValuesByFieldId": {
                        "fldPBgWW2LC9QpBmw": "HEC-COND-OBJ-NEEDLE-MINDER-ENCHANTMENT",
                        "fldXrlNVruzitWK24": "Enchanted needle minder",
                        "fldq2fRLXs5uiUVFF": linked("BLM-OBJ-000009"),
                        "fldZ3x0HnJ6cpkzkV": {"name": "Active"},
                        "fldrZZslMoyTNG1WM": "The object is enchanted.",
                        "fldNS1Mt9XjGt5HxD": "Exact behavior, activation, range and cost remain unresolved.",
                        "fldz5ndH9VeMGzIIM": {"name": "PARTIAL"},
                        "fldUdBpxSIKyiZj7I": "Episode 6 audit; object record.",
                    }
                }
            ],
        }
    )


def test_snapshot_maps_stable_practitioner_and_form_links_without_name_fuzzing():
    store = AirtableHecateStore.from_snapshot(make_snapshot())
    profile = store.get_profile(FLORENCE)
    assert profile is not None
    assert profile.form_keys == (PASSAGE, "HEC-FORM-FAC-GENERAL-REVELATION")
    assert store.get_profile("Florence Maeve MacKellar") is None


def test_snapshot_maps_active_focus_and_object_stable_ref():
    store = AirtableHecateStore.from_snapshot(make_snapshot())
    bond = store.get_focus_bond(FLORENCE, "Florence’s antique folding mirror")
    assert bond is not None and bond.is_focus is True
    assert bond.object_ref == "BLM-OBJ-000001"
    # Stable object identity is an explicit alternate lookup; no fuzzy display-name guess is required.
    assert store.get_focus_bond(FLORENCE, "BLM-OBJ-000001") == bond


def test_snapshot_preserves_explicit_nonfocus_as_supported_negative():
    store = AirtableHecateStore.from_snapshot(make_snapshot())
    bond = store.get_focus_bond(FLORENCE, "Enchanted brass leaf hairpin")
    assert bond is not None and bond.is_focus is False


def test_partial_condition_does_not_become_exact_behavior():
    store = AirtableHecateStore.from_snapshot(make_snapshot())
    condition = store.get_condition("HEC-COND-OBJ-NEEDLE-MINDER-ENCHANTMENT")
    assert condition is not None
    assert condition.subject_ref == "BLM-OBJ-000009"
    assert condition.exact_behavior_known is False
    assert condition.evidence
